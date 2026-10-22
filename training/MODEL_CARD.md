# Model card: PyMentor tutor (Track A, M6)

*Template. Filled in once the runs in `training/README.md` are done. Nothing
here is a result yet.*

## What it is

A small language model that writes short, grounded explanations and hints for
Python errors that PyMentor's engine has already found. It never detects
errors, picks line numbers or decides whether code is correct (CLAUDE.md,
principle 1). Every output is checked by `pymentor.grounding` at runtime, and
the app falls back to the rule card's own text when a check fails.

## Models

| | Base model | Licence | Parameters | int4 ONNX size |
| --- | --- | --- | --- | --- |
| Tutor A | `HuggingFaceTB/SmolLM2-360M-Instruct` | Apache-2.0 | 362M | to fill |
| Tutor B | `Qwen/Qwen2.5-Coder-0.5B-Instruct` | Apache-2.0 | ~494M | to fill |
| Teacher (data only, never shipped) | `Qwen/Qwen3-4B-Instruct-2507`, Q4_K_M GGUF | Apache-2.0 | 4B | n/a |

Confirm each licence on its Hugging Face model card when downloading, and note
the exact revision (commit hash) used: to fill.

## Training data

- Prompts: `pipeline` generate run, prompt format version 1 (D10, D38).
- Targets: drafted by the local teacher, kept only if grounded and any code
  verifies as a fix (D40). Accepted / drafted: to fill. Human review: to fill
  (`review --summary`).
- Seeds: 146 correct programs, provenance in `pipeline/corpus/DATA_CARD.md`.

## Training

Settings and hardware for each run: to fill from `training/runs/*/config.json`
and `summary.json` (steps, best validation loss, time).

## Results on benchmark v0

| Model | Grounded | Fix verified | Mean words | Over limit | p50 ms (CPU) |
| --- | --- | --- | --- | --- | --- |
| Template baseline (D12) | 100% | n/a | 18.7 | 0% | 0 |
| Tutor A, PyTorch | | | | | |
| Tutor A, int4 ONNX | | | | | |
| Tutor B, PyTorch | | | | | |
| Tutor B, int4 ONNX | | | | | |

Hand scores (clarity, hint quality, accuracy) from the sheets in
`benchmark/results/v0/`: to fill.

## Go / no-go

A tutor ships only if it stays grounded (the runtime fallback hides failures,
but a high fallback rate means the model adds nothing), scores better than the
template by hand, and its download size and browser latency are acceptable on
a budget laptop (M8).

## Limitations

To fill: known failure patterns from the hand review.
