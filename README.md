# An Empirical Benchmark of Supervised Fine-tuned Models for Natural-Language-to-VHDL Generation of Embedded System Components

This repository contains the artifacts associated with the paper:

> **"An Empirical Benchmark of Supervised Fine-tuned Models for Natural-Language-to-VHDL Generation of Embedded System Components"**
> Pietro Liguori, Alessandra De Benedictis, Gaetano Prisco, Domenico Cotroneo
> *Journal of Systems Architecture*, 2026

---

## Repository Structure

```
├── taxonomy/
│   ├── categories_legend.txt     # Description of the 31 architectural categories
│   └── categories_distrib.txt    # Category distribution across the corpus (aggregate counts)
│
├── models_output/                # Generated VHDL for the paper's test set (326 samples)
│   ├── fine-tuned-SLMs/
│   │   ├── CodeGen/ CodeGPT/ CodeT5p_220/ CodeT5p_770/ PLBART/
│   │   │   └── {finetuned, pretrained-30k}/ (hyps.txt, refs.txt)
│   │   ├── deepseek-coder-1.3b.out    # New backbones added in the revision
│   │   ├── qwen2.5-coder-1.5b.out
│   │   └── starcoder2-3b.out
│   └── non-fine-tuned-LLMs/           # Zero-/five-shot outputs of the LLM baselines
│
├── scripts/                      # Automatic evaluation scripts
│   ├── output_similarity_metrics.py   # ED, BLEU-1..4, CrystalBLEU, ROUGE, METEOR, EM
│   ├── crystal_bleu.py                # CrystalBLEU (Pygments VHDL lexer, per-sample)
│   └── bleu_score.py                  # BLEU implementation (Google, Apache-2.0)
│
├── verilogeval_vhdl/             # Cross-benchmark evaluation on VerilogEval v2
│   ├── translate_prompts.py           # Deterministic Verilog->VHDL prompt translation
│   ├── generate_codet5p.py            # Generation with fine-tuned CodeT5+ 770M
│   ├── generate_mlx.py                # Generation with the MLX fine-tuned backbones
│   ├── cosim.py                       # Differential golden-vector co-simulation
│   ├── results_<model>.csv            # Per-problem verdicts for each model
│   └── generated_outputs/<model>/     # Generated VHDL, one file per problem
│
└── lora_adapters/                # LoRA adapters of the newly fine-tuned backbones
    ├── qwen/  deepseek/  starcoder2/  (adapters.safetensors, adapter_config.json)
```

---

## Dataset (restricted access)

The supervised fine-tuning corpus (≈3,000 expert-curated NL–VHDL pairs, split into
2,364 training / 282 validation / 326 test pairs) is **not included in this repository**:
it is provided under restricted access due to industrial confidentiality. It is available
upon reasonable request to the corresponding author.

Non-confidential information about the dataset:

- The supervised unit is the **complete NL–VHDL pair**; the train/validation/test splits are
  pair-level disjoint after normalisation, so no complete test pair was exposed during
  pre-training, fine-tuning, model selection, or baseline evaluation.
- The test set (326 pairs) is stratified across the **31 architectural categories** described
  in [`taxonomy/categories_legend.txt`](taxonomy/categories_legend.txt); the aggregate
  per-category distribution is in [`taxonomy/categories_distrib.txt`](taxonomy/categories_distrib.txt).
- The unsupervised corpus used for Domain-Adaptive Pre-training (≈36,500 VHDL samples) is
  publicly available at [AWfaw/ai-hdlcoder-dataset-clean](https://huggingface.co/datasets/AWfaw/ai-hdlcoder-dataset-clean)
  and is therefore not redistributed here.

---

## Model Outputs

The `models_output/` directory contains the generated VHDL outputs for all models evaluated
in the paper, line-aligned with the 326-sample test set.

### Fine-tuned SLMs (`fine-tuned-SLMs/`)

**Original backbones** (CodeGen, CodeGPT, CodeT5+ 220M, CodeT5+ 770M, PLBART). Each model
directory contains one or two configurations:

| Folder | Description |
|--------|-------------|
| `finetuned/` | Supervised Fine-Tuning (SFT) only |
| `pretrained-30k/` | Domain-Adaptive Pre-training (30k steps) followed by SFT |

Within each configuration, `hyps.txt` holds the model-generated outputs and `refs.txt` the
corresponding references, line-aligned. CodeT5+ 770M has only the SFT configuration
(DAP was not applied due to the 6 GB VRAM budget of the original setup).

**Recent code-specialised backbones** (`deepseek-coder-1.3b.out`, `qwen2.5-coder-1.5b.out`,
`starcoder2-3b.out`): added during the revision, fine-tuned with the same LoRA recipe
(rank 8, base non-instruct checkpoints, same training split) on a consumer-grade
single-device setup (Apple M1 Max, [MLX](https://github.com/ml-explore/mlx) framework):
~3 epochs (900 iterations, batch 8), learning rate 1e-4, max sequence length 512, seed 42,
greedy decoding. Each `.out` file contains one generated output per line, aligned with the
326-sample test set. The reference outputs are the same test references for all models and
are provided as `refs.txt` under `models_output/fine-tuned-SLMs/` (the per-folder copies are
line-aligned and differ only in minor whitespace around punctuation).

### Non-Fine-Tuned LLMs (`non-fine-tuned-LLMs/`)

Large-scale baselines that were **not** fine-tuned in our protocol: the closed-weight
commercial systems and the large open-weight Command R+ (grouped here because fine-tuning a
≈104B-parameter model is infeasible under our hardware budget, not because its weights are
unavailable).

- **Zero-shot outputs** (`claude_sonnet-3_5.out`, `command+.out`, `github_copilot.out`,
  `GPT-3_5.out`, `GPT-4.out`, `GPT-4o.out`): collected during the first half of 2025.
- **Zero- and five-shot outputs of the recent models** (`claude_sonnet-5.out`,
  `claude_sonnet-5-few_shot.out`, `GPT-5.5.out`, `GPT-5.5-few_shot.out`): collected in
  July 2026.

All zero-shot runs use the standardized minimal prompt
*"Generate a syntactically correct VHDL module implementing the following specification:"*.
The five-shot runs prepend five fixed demonstrations drawn exclusively from the training
split (full template in Appendix A of the paper).

---

## Evaluation Scripts (`scripts/`)

`output_similarity_metrics.py` computes all the automatic metrics reported in the paper
(Edit Distance, BLEU-1..4, CrystalBLEU, ROUGE-1..4/L, METEOR, Exact Match) for a hypothesis
file against a reference file. CrystalBLEU follows Eghbali & Pradel (ASE 2022) and is
computed per sample with VHDL-aware tokenization (Pygments lexer), using the k=500 most
frequent n-grams (n=1..4) of the corpus as trivially shared n-grams.

```bash
pip install evaluate pylcs rouge nltk numpy crystalbleu pygments
python scripts/output_similarity_metrics.py <hypothesis_file>
```

Note: the reference path at the top of `output_similarity_metrics.py` should be pointed to
one of the provided reference files (e.g.,
`models_output/fine-tuned-SLMs/CodeT5p_770/finetuned/refs.txt`). Recomputing CrystalBLEU
additionally requires the training/validation corpus files (restricted dataset package),
which are used to extract the trivially shared n-grams.

---

## Cross-Benchmark Evaluation: VerilogEval → VHDL (`verilogeval_vhdl/`)

Evaluation of the fine-tuned models on the [VerilogEval v2](https://github.com/NVlabs/verilog-eval)
spec-to-RTL problems, deterministically translated to VHDL:

- **Prompt translation** (`translate_prompts.py`): only the interface syntax is changed
  (module → entity, port list → VHDL port declarations, in both a verbose and a single-line
  "dataset-style" rendering); port names that collide with VHDL reserved words are renamed
  with a deterministic rule (e.g., `out` → `out_p`). Problems that embed Verilog source in
  the prompt (3 bug-fixing tasks) are excluded; `Prob031_dff` is not evaluable due to an
  upstream prompt defect (it declares `q` as an input), leaving **152 evaluable problems**.
  The VerilogEval problem files are not redistributed here: the script regenerates the
  translated prompts from an upstream checkout.
- **Functional verification** (`cosim.py`): differential golden-vector co-simulation — the
  Verilog reference is simulated with Icarus Verilog and the generated VHDL with GHDL under
  identical, seeded stimuli (exhaustive for ≤8 input bits, 256 random vectors otherwise,
  100 clocked cycles with reset handling for sequential designs); output traces are compared
  bit by bit. Each design is also checked with `ghdl synth`.

Results (pass@1, greedy decoding, 152 evaluable problems):

| Model (fine-tuned) | Functional PASS | Synthesizable (GHDL) |
|---|---|---|
| DeepSeek-Coder 1.3B | 22/152 (14.5%) | 74/152 (48.7%) |
| CodeT5+ 770M | 9/152 (5.9%) | 67/152 (44.1%) |
| Qwen2.5-Coder 1.5B | 0/152 | 1/152 |
| StarCoder2 3B | 0/152 | 0/152 |

Per-problem verdicts, with an exhaustive failure taxonomy (functional-fail, analysis-error,
sim-error, interface-mismatch, elaboration-error, no-entity), are in `results_<model>.csv`;
the generated VHDL is in `generated_outputs/<model>/`.

Requirements: `ghdl`, `iverilog` on the PATH; a checkout of the upstream VerilogEval
repository (path configured at the top of `translate_prompts.py`).

---

## LoRA Adapters (`lora_adapters/`)

Final LoRA adapters (rank 8) of the three backbones fine-tuned during the revision, in
[MLX](https://github.com/ml-explore/mlx-examples/tree/main/llms) format:

| Folder | Base model |
|---|---|
| `qwen/` | [Qwen/Qwen2.5-Coder-1.5B](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B) |
| `deepseek/` | [deepseek-ai/deepseek-coder-1.3b-base](https://huggingface.co/deepseek-ai/deepseek-coder-1.3b-base) |
| `starcoder2/` | [bigcode/starcoder2-3b](https://huggingface.co/bigcode/starcoder2-3b) |

Example usage:

```bash
pip install mlx-lm
python -m mlx_lm generate --model Qwen/Qwen2.5-Coder-1.5B \
    --adapter-path lora_adapters/qwen \
    --prompt "-- Define a circuit named TopModule with the signal a as input ..."
```

---

## Interactive Demo

A quantized version of the best-performing model (CodeT5+ 770M) is publicly available as an
interactive VHDL code generator:

🔗 [https://huggingface.co/spaces/OSS-forge/vhdl-codegen-demo](https://huggingface.co/spaces/OSS-forge/vhdl-codegen-demo)

> **Note:** The demo uses a quantized variant of the model to meet deployment constraints.
> Minor differences in output quality compared to the results reported in the paper may be
> observed.

---

## Citation

If you use these artifacts in your research, please cite:

```bibtex
@article{liguori2026vhdl,
  title   = {An Empirical Benchmark of Supervised Fine-tuned Models for
             Natural-Language-to-VHDL Generation of Embedded System Components},
  author  = {Liguori, Pietro and De Benedictis, Alessandra and
             Prisco, Gaetano and Cotroneo, Domenico},
  journal = {Journal of Systems Architecture},
  year    = {2026}
}
```

---

## License and Access

The NL–VHDL dataset is distributed as a **separate package under restricted access**, due to
confidentiality terms agreed with our industry partner (see the Dataset section above).

`scripts/bleu_score.py` is derived from Google's BLEU implementation (Apache License 2.0).
The VerilogEval benchmark referenced by `verilogeval_vhdl/` is © NVIDIA (Apache License 2.0)
and is not redistributed here.

For any questions regarding access or use of these materials, please contact the
corresponding author at `pietro.liguori@unina.it`.
