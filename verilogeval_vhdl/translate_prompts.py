"""Deterministically translate VerilogEval v2 spec-to-RTL prompts to VHDL.

Only the interface syntax is changed (module -> entity, port list ->
VHDL port declarations); the natural-language body is left untouched.
"""
import os
import re
import sys

# path to an upstream checkout of https://github.com/NVlabs/verilog-eval
SCR = os.environ.get(
    "VERILOG_EVAL_DIR", "verilog-eval/dataset_spec-to-rtl")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "problems")

import glob

# all spec-to-RTL problems whose interface is expressed in the standard
# NL port-list format; problems that embed Verilog source in the prompt
# (bug-fixing tasks) yield no parsed ports and are excluded.
SUBSET = sorted(
    os.path.basename(f).replace("_prompt.txt", "")
    for f in glob.glob(os.path.join(SCR, "*_prompt.txt")))

PORT_RE = re.compile(
    r"^\s*-\s*(input|output)\s+(\w+)\s*"
    r"(?:\(\s*(\d+)\s*bits?\s*\))?\s*,?\s*$")

# deterministic rename rule for port names that are VHDL reserved words
VHDL_RESERVED = {
    "out", "in", "is", "and", "or", "not", "buffer", "register", "signal",
    "all", "begin", "end", "use", "map", "of", "then", "when", "select",
}


def safe_name(name):
    return f"{name}_p" if name.lower() in VHDL_RESERVED else name


def parse_ports(prompt):
    ports = []
    for line in prompt.splitlines():
        m = PORT_RE.match(line)
        if m:
            direction, name, width = m.group(1), m.group(2), m.group(3)
            ports.append((name, direction, int(width) if width else 1))
    return ports


def vhdl_port_line(name, direction, width):
    d = "in" if direction == "input" else "out"
    typ = ("std_logic" if width == 1
           else f"std_logic_vector({width - 1} downto 0)")
    return f" - {safe_name(name)} : {d} {typ}"


def translate(prompt):
    ports = parse_ports(prompt)
    out_lines = []
    for line in prompt.splitlines():
        m = PORT_RE.match(line)
        if m:
            name, width = m.group(2), int(m.group(3)) if m.group(3) else 1
            out_lines.append(vhdl_port_line(name, m.group(1), width))
        else:
            line = line.replace(
                "implement a module named TopModule",
                "implement a VHDL design (entity and architecture) named "
                "TopModule")
            line = line.replace(
                "All input and output ports are one bit unless otherwise",
                "The interface, in VHDL syntax, is the following (use the "
                "IEEE std_logic_1164 types")
            line = line.replace("specified.", "as specified).")
            out_lines.append(line)
    return "\n".join(out_lines), ports


def behavioral_text(prompt):
    """The NL body after the interface list, collapsed to one line."""
    lines = prompt.splitlines()
    last_port = max(i for i, l in enumerate(lines) if PORT_RE.match(l))
    body = " ".join(l.strip() for l in lines[last_port + 1:] if l.strip())
    return body


def translate_short(prompt):
    """Single-line, dataset-style prompt (same register as Category 31):
    'Define a circuit named X with the signal A as input and ...'"""
    ports = parse_ports(prompt)

    def sig(name, width):
        pre = f"the {width}-bit signal" if width > 1 else "the signal"
        return f"{pre} {safe_name(name)}"

    ins = [sig(n, w) for n, d, w in ports if d == "input"]
    outs = [sig(n, w) for n, d, w in ports if d == "output"]

    def join(items, direction):
        suff = direction + ("s" if len(items) > 1 else "")
        if len(items) == 1:
            return f"{items[0]} as {suff}"
        return f"{', '.join(items[:-1])} and {items[-1]} as {suff}"

    clauses = [join(lst, d) for lst, d in ((ins, "input"), (outs, "output"))
               if lst]
    return (f"Define a circuit named TopModule with "
            f"{' and '.join(clauses)}. {behavioral_text(prompt)}")


def main():
    os.makedirs(OUT, exist_ok=True)
    import json
    meta = {}
    excluded = []
    for prob in SUBSET:
        prompt = open(f"{SCR}/{prob}_prompt.txt").read()
        if not parse_ports(prompt):
            excluded.append(prob)
            continue
        vhdl_prompt, ports = translate(prompt)
        with open(f"{OUT}/{prob}_vhdl_prompt.txt", "w") as f:
            f.write(vhdl_prompt)
        with open(f"{OUT}/{prob}_vhdl_prompt_short.txt", "w") as f:
            f.write(translate_short(prompt) + "\n")
        # keep the reference verilog next to it for the golden simulation
        ref = open(f"{SCR}/{prob}_ref.sv").read()
        with open(f"{OUT}/{prob}_ref.sv", "w") as f:
            f.write(ref)
        meta[prob] = {"ports": [{"name": n, "vhdl_name": safe_name(n),
                                 "dir": d, "width": w}
                                for n, d, w in ports],
                      "sequential": any(n == "clk" for n, _d, _w in ports)}
    with open(f"{OUT}/meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"{len(meta)} prompt tradotti -> {OUT}")
    print(f"{len(excluded)} esclusi (codice Verilog nel prompt): {excluded}")


if __name__ == "__main__":
    sys.exit(main())
