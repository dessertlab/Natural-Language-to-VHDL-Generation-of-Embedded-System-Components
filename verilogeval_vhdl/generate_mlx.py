"""Generate VHDL for the VerilogEval subset with the MLX fine-tuned SLMs."""
import json
import os
import sys

from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)

# NOTE: the official deepseek-ai repo ships no safetensors; use the
# mlx-community conversion (weights.00.safetensors renamed to
# model.safetensors) as the base model for MLX.
MODELS = {
    "qwen2.5-coder-1.5b": ("Qwen/Qwen2.5-Coder-1.5B",
                           f"{ROOT}/lora_adapters/qwen"),
    "deepseek-coder-1.3b": ("mlx-community/deepseek-coder-1.3b-base-mlx",
                            f"{ROOT}/lora_adapters/deepseek"),
    "starcoder2-3b": ("bigcode/starcoder2-3b",
                      f"{ROOT}/lora_adapters/starcoder2"),
}


def main():
    meta = json.load(open(f"{BASE}/problems/meta.json"))
    sampler = make_sampler(temp=0.0)
    for label, (model_id, adapter) in MODELS.items():
        out_dir = f"{BASE}/generated_outputs/{label}"
        os.makedirs(out_dir, exist_ok=True)
        model, tok = load(model_id, adapter_path=adapter)
        only = os.environ.get("ONLY_PROBLEMS", "").split()
        for prob in [p for p in sorted(meta) if not only or p in only]:
            nl = open(f"{BASE}/problems/{prob}_vhdl_prompt_short.txt"
                      ).read().strip()
            text = generate(model, tok, prompt=f"-- {nl}\n",
                            max_tokens=768, sampler=sampler)
            code = text.strip().split("\n")[0].strip()
            with open(f"{out_dir}/{prob}.vhd", "w") as f:
                f.write(code + "\n")
            print(f"{label} {prob}: {len(code)} chars", flush=True)
        del model


if __name__ == "__main__":
    sys.exit(main())
