"""Differential golden-vector co-simulation for the VerilogEval pilot.

For each problem:
  1. Python generates a deterministic stimulus set (seeded).
  2. The Verilog reference (RefModule) is simulated with Icarus Verilog,
     dumping one line of output values per vector -> golden trace.
  3. The generated VHDL is simulated with GHDL (VHDL-2008) under the same
     stimuli -> candidate trace.
  4. Traces are compared bit-by-bit; the design also goes through
     `ghdl synth` for a synthesizability verdict.

Usage: cosim.py <gen_dir>   (e.g. verilogeval/gen/codet5p-770m)
"""
import csv
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
GHDL = shutil.which("ghdl")
IVERILOG = shutil.which("iverilog")
VVP = shutil.which("vvp")
SEED = 42
N_RANDOM = 256
N_CYCLES = 100
IEEE_CTX = ("library ieee;\nuse ieee.std_logic_1164.all;\n"
            "use ieee.numeric_std.all;\n")


def gen_stimuli(ports, sequential):
    rng = random.Random(SEED)
    ins = [p for p in ports if p["dir"] == "input" and p["name"] != "clk"]
    total_bits = sum(p["width"] for p in ins)
    vectors = []
    if not sequential and total_bits <= 8:
        for val in range(2 ** total_bits):
            vec, shift = {}, 0
            for p in ins:
                vec[p["name"]] = (val >> shift) & ((1 << p["width"]) - 1)
                shift += p["width"]
            vectors.append(vec)
    else:
        n = N_CYCLES if sequential else N_RANDOM
        for cyc in range(n):
            vec = {}
            for p in ins:
                name = p["name"].lower()
                if re.fullmatch(r"a?reset|a?rst", name):
                    # active-high reset: asserted at start, sporadic after
                    vec[p["name"]] = 1 if (cyc < 2 or rng.random() < 0.1) \
                        else 0
                elif re.fullmatch(r"a?reset_?n|a?rst_?n", name):
                    # active-low reset: same policy, inverted
                    vec[p["name"]] = 0 if (cyc < 2 or rng.random() < 0.1) \
                        else 1
                else:
                    vec[p["name"]] = rng.getrandbits(p["width"])
            vectors.append(vec)
    return ins, vectors


def bits(val, width):
    return format(val, f"0{width}b")


# ---------------------------------------------------------------- verilog --
def write_verilog_tb(path, ports, ins, outs, vectors, sequential):
    decl, conn = [], []
    for p in ports:
        n, w = p["name"], p["width"]
        conn.append(f".{n}({n})")
        if n == "clk":
            continue  # declared by the clock generator
        rng_s = f"[{w - 1}:0] " if w > 1 else ""
        decl.append(f"  {'reg' if p['dir'] == 'input' else 'wire'} "
                    f"{rng_s}{n};")
    fmt = ",".join("%b" for _ in outs)
    args = ", ".join(p["name"] for p in outs)
    apply_tpl = "\n".join(
        f"      {p['name']} = {p['width']}'b%({p['name']})s;" for p in ins)
    body = []
    for vec in vectors:
        assigns = apply_tpl % {k: bits(v, next(p["width"] for p in ins
                                               if p["name"] == k))
                               for k, v in vec.items()}
        if sequential:
            body.append(f"      @(negedge clk);\n{assigns}\n"
                        f"      @(posedge clk); #1;\n"
                        f'      $display("{fmt}", {args});')
        else:
            body.append(f"{assigns}\n      #1;\n"
                        f'      $display("{fmt}", {args});')
    clk = ("  reg clk = 0;\n  always #5 clk = ~clk;\n"
           if sequential else "")
    with open(path, "w") as f:
        f.write(f"""`timescale 1ns/1ps
module tb;
{clk}{os.linesep.join(decl)}
  RefModule dut ({", ".join(conn)});
  initial begin
{os.linesep.join(body)}
      $finish;
  end
endmodule
""")


# ------------------------------------------------------------------- vhdl --
def to_str_expr(p):
    n = p["vhdl_name"]
    return f"to_string({n})"


def write_vhdl_tb(path, entity, ports, ins, outs, vectors, sequential):
    decl, conn = [], []
    for p in ports:
        n, w = p["vhdl_name"], p["width"]
        conn.append(f"{n} => {n}")
        if n == "clk":
            continue  # declared by the clock generator
        typ = "std_logic" if w == 1 else \
            f"std_logic_vector({w - 1} downto 0)"
        decl.append(f"  signal {n} : {typ};")
    stim_decl, stim_assign = [], []
    for p in ins:
        n, w = p["vhdl_name"], p["width"]
        lits = ", ".join(f'"{bits(v[p["name"]], w)}"' for v in vectors)
        stim_decl.append(
            f"  type t_{n} is array (0 to {len(vectors) - 1}) of "
            f"std_logic_vector({w - 1} downto 0);\n"
            f"  constant stim_{n} : t_{n} := ({lits});")
        tgt = f"{n} <= stim_{n}(i)(0);" if w == 1 else \
            f"{n} <= stim_{n}(i);"
        stim_assign.append(f"      {tgt}")
    outs_expr = ' & "," & '.join(to_str_expr(p) for p in outs)
    clk_decl = "  signal clk : std_logic := '0';\n" if sequential else ""
    clk_proc = "  clk <= not clk after 5 ns;\n" if sequential else ""
    nl = "\n"
    if sequential:
        step = (f"      wait until falling_edge(clk);{nl}"
                f"{nl.join(stim_assign)}{nl}"
                f"      wait until rising_edge(clk);{nl}"
                f"      wait for 1 ns;{nl}"
                f"      write(cosim_l, {outs_expr});{nl}"
                f"      writeline(output, cosim_l);")
    else:
        step = (f"{nl.join(stim_assign)}{nl}"
                f"      wait for 1 ns;{nl}"
                f"      write(cosim_l, {outs_expr});{nl}"
                f"      writeline(output, cosim_l);")
    with open(path, "w") as f:
        f.write(f"""library ieee;
use ieee.std_logic_1164.all;
use std.textio.all;
use std.env.finish;

entity tb is end entity;
architecture sim of tb is
{clk_decl}{nl.join(decl)}
{nl.join(stim_decl)}
begin
{clk_proc}  dut : entity work.{entity} port map ({", ".join(conn)});
  process
    variable cosim_l : line;
  begin
    for i in 0 to {len(vectors) - 1} loop
{step}
    end loop;
    finish;
  end process;
end architecture;
""")


# ------------------------------------------------------------------- runs --
def run(cmd, cwd, timeout=120):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


def norm_trace(text):
    rows = []
    for line in text.splitlines():
        line = line.strip().lower()
        if line and re.fullmatch(r"[01xzuw,\-]+", line):
            rows.append(line.split(","))
    return rows


def check_problem(prob, m, gen_file, workdir):
    ports = m["ports"]
    seq = m["sequential"]
    ins, vectors = gen_stimuli(ports, seq)
    outs = [p for p in ports if p["dir"] == "output"]

    # --- golden (icarus)
    write_verilog_tb(f"{workdir}/tb.sv", ports, ins, outs, vectors, seq)
    shutil.copy(f"{BASE}/problems/{prob}_ref.sv", f"{workdir}/ref.sv")
    r = run([IVERILOG, "-g2012", "-o", "golden.vvp", "ref.sv", "tb.sv"],
            workdir)
    if r.returncode != 0:
        return {"result": "golden-compile-error",
                "detail": r.stderr.strip()[:120]}
    r = run([VVP, "golden.vvp"], workdir)
    golden = norm_trace(r.stdout)

    # --- candidate (ghdl); on a context-import failure, retry with the
    # missing standard packages prepended (recorded as ctx_repair)
    base_code = open(gen_file).read()
    if "library ieee" not in base_code.lower():
        base_code = IEEE_CTX + base_code
    em = re.search(r"\bentity\s+(\w+)\s+is\b", base_code, re.I)
    if not em:
        return {"result": "no-entity", "detail": ""}
    entity = em.group(1)
    variants = [
        ("", base_code),
        ("numeric_std", "library ieee; use ieee.numeric_std.all;\n"
         + base_code),
        ("std_logic_unsigned",
         "library ieee; use ieee.std_logic_unsigned.all;\n" + base_code),
    ]
    err = None
    ctx_repair = None
    for tag, code in variants:
        open(f"{workdir}/gen.vhd", "w").write(code + "\n")
        r = run([GHDL, "-a", "--std=08", "-frelaxed", "-fsynopsys",
                 "gen.vhd"], workdir)
        if r.returncode == 0:
            ctx_repair = tag
            break
        err = r.stderr.strip()[:120]
    else:
        return {"result": "analysis-error", "detail": err}
    write_vhdl_tb(f"{workdir}/tb.vhd", entity, ports, ins, outs, vectors,
                  seq)
    for step_cmd, stage in ((["-a", "--std=08", "-frelaxed", "-fsynopsys",
                              "tb.vhd"], "tb-analysis"),
                            (["-e", "--std=08", "-frelaxed", "-fsynopsys",
                              "tb"], "elaboration")):
        r = run([GHDL] + step_cmd, workdir)
        if r.returncode != 0:
            res = ("interface-mismatch" if stage == "tb-analysis"
                   else f"{stage}-error")
            return {"result": res, "ctx_repair": ctx_repair,
                    "detail": r.stderr.strip()[:120]}
    r = run([GHDL, "-r", "--std=08", "-frelaxed", "-fsynopsys", "tb"],
            workdir, timeout=180)
    cand = norm_trace(r.stdout)

    # --- synthesizability
    rs = run([GHDL, "synth", "--std=08", "-frelaxed", "-fsynopsys",
              "--latches", entity], workdir)
    synth_ok = rs.returncode == 0

    # --- compare
    if len(cand) < len(golden):
        return {"result": "sim-error", "synth": synth_ok,
                "ctx_repair": ctx_repair,
                "detail": f"trace {len(cand)}/{len(golden)}"}
    mism = 0
    for g_row, c_row in zip(golden, cand):
        for g, c in zip(g_row, c_row):
            if any(ch not in "01" for ch in g):
                continue  # golden don't-care
            if g != c:
                mism += 1
                break
    if mism == 0:
        return {"result": "PASS", "synth": synth_ok,
                "ctx_repair": ctx_repair,
                "detail": f"{len(golden)} vettori"}
    return {"result": "functional-fail", "synth": synth_ok,
            "ctx_repair": ctx_repair,
            "detail": f"{mism}/{len(golden)} vettori errati"}


def main():
    gen_dir = sys.argv[1]
    label = os.path.basename(gen_dir.rstrip("/"))
    meta = json.load(open(f"{BASE}/problems/meta.json"))
    rows = []
    for prob in sorted(meta):
        gen_file = f"{gen_dir}/{prob}.vhd"
        if not os.path.exists(gen_file):
            continue
        with tempfile.TemporaryDirectory() as wd:
            try:
                res = check_problem(prob, meta[prob], gen_file, wd)
            except subprocess.TimeoutExpired:
                res = {"result": "timeout", "detail": ""}
        rows.append({"problem": prob, **res})
        rep = res.get('ctx_repair') or ''
        print(f"{prob}: {res['result']} "
              f"(synth={res.get('synth', '-')}"
              f"{', repair=' + rep if rep else ''}) "
              f"{res.get('detail', '')}", flush=True)
    out = f"{BASE}/results_{label}.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["problem", "result", "synth",
                                          "ctx_repair", "detail"])
        w.writeheader()
        w.writerows(rows)
    n_pass = sum(r["result"] == "PASS" for r in rows)
    n_synth = sum(r.get("synth") is True for r in rows)
    print(f"\n{label}: PASS funzionale {n_pass}/{len(rows)} | "
          f"sintetizzabili {n_synth}/{len(rows)} -> {out}")


if __name__ == "__main__":
    main()
