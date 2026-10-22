# pymentor-training

The tutor model (M6, later M7): fine-tune a small open-weight model on drafted
answers, score it on the benchmark, and export it to int4 ONNX for the browser.
Everything runs on your own machine and costs nothing (D40).

| Module | What it does |
| --- | --- |
| `data.py` | Drafts to token ids; the prompt's section markers become special tokens; loss on the answer only |
| `sft.py` | The fine-tuning loop: resumable, best-by-validation checkpoint, low-memory options |
| `infer.py` | `Tutor`: a trained model (PyTorch or ONNX) as a callable for the evaluation harness |
| `export.py` | ONNX export plus 4-bit quantisation, in the layout transformers.js loads |

The models (D42): tutors **SmolLM2-360M-Instruct** and
**Qwen2.5-Coder-0.5B-Instruct**, compared on quality against download size;
teacher **Qwen3-4B-Instruct-2507**. All Apache-2.0.

## Runbook: your laptop, start to finish

Each step is resumable, so it's fine to stop and carry on later. Commands run
from the repo root.

### 0. Check the GPU is free

```bash
nvidia-smi        # the RTX 3050 here has 4 GB; everything below is set for that
```

Close anything else using the GPU (games, other notebooks) before steps 3 and 6.

### 1. Set up (once)

```bash
uv venv -p 3.14 .venv && source .venv/bin/activate
uv pip install torch                      # the default build includes CUDA
uv pip install -e engine -e pipeline -e "training[dev]"
pytest engine pipeline training           # everything should pass
```

### 2. Make the prompts

```bash
python -m pymentor_pipeline generate      # ~1 minute; data/generated/v1/, not committed
```

### 3. Start the teacher

Install [llama.cpp](https://github.com/ggml-org/llama.cpp) and download a
`Q4_K_M` GGUF of Qwen3-4B-Instruct-2507 (about 2.5 GB) from Hugging Face.
Check the licence on the model card says Apache-2.0. Then:

```bash
llama-server -m Qwen3-4B-Instruct-2507-Q4_K_M.gguf --port 8080 -ngl 99 -c 4096
```

`-ngl 99` puts every layer on the GPU. Ollama works too: pass its address to
`draft` with `--url http://127.0.0.1:11434/v1/chat/completions` and its model
name with `--model`.

### 4. Trial run: 500 answers, then look at them

```bash
python -m pymentor_pipeline draft --model qwen3-4b-instruct-2507 --limit 500
python -m pymentor_pipeline review --sample 50
```

`draft` prints how many answers passed grounding and fix verification; the
rest are in `rejected-train.jsonl` with reasons. `review` shows answers one at
a time for a yes/no. Note the time per answer: it tells you how long the full
run takes. If most are rejected or reviewed as bad, stop here and tell me what
you see; the teacher's instructions can be tuned.

### 5. The full drafting run

```bash
python -m pymentor_pipeline draft --model qwen3-4b-instruct-2507 --limit 15000
python -m pymentor_pipeline draft --model qwen3-4b-instruct-2507 --split val --limit 1500
```

The order is balanced across cards, so any amount is a fair sample. Leave it
running overnight; if it stops, the same command carries on.

### 6. Fine-tune both tutors

Stop the teacher first (`Ctrl+C` in its terminal): on a 4 GB GPU, training
needs all of it. These settings are for 4 GB and are starting points, not yet
tested on a real GPU, so compare the validation loss in each run's
`log.jsonl` and tell me how it went.

```bash
# SmolLM2-360M: about 2.5 GB estimated
python -m pymentor_training train --base HuggingFaceTB/SmolLM2-360M-Instruct \
  --data data/generated/v1 --out training/runs/smollm2-360m \
  --step-in-backward --grad-accum 1 --optimizer adafactor --gradient-checkpointing \
  --batch-size 8 --lr 5e-5 --epochs 3

# Qwen2.5-Coder-0.5B: about 3.4 GB estimated, so close everything else on the GPU
python -m pymentor_training train --base Qwen/Qwen2.5-Coder-0.5B-Instruct \
  --data data/generated/v1 --out training/runs/qwen-coder-0.5b \
  --step-in-backward --grad-accum 1 --optimizer adafactor --gradient-checkpointing \
  --batch-size 2 --lr 3e-5 --epochs 3
```

`--step-in-backward` updates each weight as soon as its gradient is ready and
then frees it, so a full set of gradients never exists (D44). The batch you
set is then the whole batch, since there's no gradient accumulation. Add
`--resume` to continue an interrupted run. Out of memory? Halve
`--batch-size`, or lower `--max-length` (1,024 by default). Prompts run to at
most about 1,600 characters (700 is typical), so most examples are a few
hundred tokens; `train` reports how many were too long and skipped. If
Qwen still doesn't fit, `--dtype bf16` halves its weights, at some risk that
small updates round away.

### 7. Score, export, score again

```bash
python -m pymentor_training evaluate --model training/runs/smollm2-360m/best --name smollm2-360m-sft
python -m pymentor_training export --model training/runs/smollm2-360m/best --out training/runs/smollm2-360m/web
python -m pymentor_training evaluate --model training/runs/smollm2-360m/web \
  --onnx model_q4.onnx --name smollm2-360m-sft-q4
```

Repeat for `qwen-coder-0.5b`. Results land in `benchmark/results/v0/`, next to
the template baseline. Commit those JSON and CSV files (never the weights,
which `.gitignore` keeps out), then fill in the hand-scoring sheets.

## Memory guide (4 GB)

`train` prints an estimate before it starts. With the settings above (fp32
weights, Adafactor, `--step-in-backward`), the weights take 4 bytes a
parameter, Adafactor's state a fraction of that, and gradients only the
largest single tensor (the vocabulary table):

| | Weights | Optimizer | Gradients | Plus | Estimate |
| --- | --- | --- | --- | --- | --- |
| SmolLM2-360M | 1.45 GB | ~0.15 GB | 0.19 GB | CUDA ~0.4 GB, activations | ~2.5 GB |
| Qwen2.5-Coder-0.5B | 1.98 GB | ~0.2 GB | 0.54 GB | CUDA ~0.4 GB, activations | ~3.4 GB |

Two things keep activations small: gradient checkpointing, and scoring the
vocabulary only at the answer's positions (`answer_loss`), which matters most
for Qwen's 152k vocabulary. Without `--step-in-backward`, add a full copy of
the weights for the gradients, which is too much for Qwen on 4 GB.
