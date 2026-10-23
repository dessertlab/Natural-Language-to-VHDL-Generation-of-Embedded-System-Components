"""Generate VHDL for the translated VerilogEval subset with the paper's
fine-tuned CodeT5+ 770M (OSS-forge/codet5p-770m-vhdl), greedy decoding."""
import json
import os
import sys
import time

import torch
from transformers import AutoTokenizer, T5ForConditionalGeneration

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = "OSS-forge/codet5p-770m-vhdl"


def main():
    meta = json.load(open(f"{BASE}/problems/meta.json"))
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = T5ForConditionalGeneration.from_pretrained(
        MODEL, torch_dtype=torch.float32).to(device).eval()

    style = sys.argv[1] if len(sys.argv) > 1 else "short"
    suffix = "_short" if style == "short" else ""
    os.makedirs(f"{BASE}/generated_outputs/codet5p-770m", exist_ok=True)
    only = os.environ.get("ONLY_PROBLEMS", "").split()
    probs = [p for p in sorted(meta) if not only or p in only]
    for i, prob in enumerate(probs):
        prompt = open(f"{BASE}/problems/{prob}_vhdl_prompt{suffix}.txt"
                      ).read().strip()
        enc = tok(prompt, return_tensors="pt", truncation=True,
                  max_length=512).to(device)
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=512, num_beams=1,
                                 do_sample=False)
        text = tok.decode(out[0], skip_special_tokens=True)
        with open(f"{BASE}/generated_outputs/codet5p-770m/{prob}.vhd", "w") as f:
            f.write(text + "\n")
        print(f"[{i + 1}/{len(probs)}] {prob} ({time.time() - t0:.0f}s, "
              f"{len(text)} chars)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
