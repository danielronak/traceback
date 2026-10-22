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

The models (D42, D45): three small tutors, **SmolLM2-135M-Instruct**,
**SmolLM2-360M-Instruct** and **Qwen2.5-Coder-0.5B-Instruct**, compared on
quality against download size (135M is the phone-sized end); the teacher,
**Qwen3-4B-Instruct-2507**, only writes training answers and never ships. All
Apache-2.0.

## Runbook: your laptop, start to finish

Written for the owner's laptop: Windows 11, an RTX 3050 with 4 GB, Git,
Python and uv already installed. Commands are for **PowerShell**, run from the
repo folder; a backtick (`` ` ``) at the end of a line continues the command on
the next line. Every step can be stopped and resumed. When a step says "send
me", paste the output into the chat.

### 1. Set up (once, about 15 minutes)

If you cloned the repo before 22 October 2026, delete that folder and clone it
again: older Windows checkouts have the wrong line endings for the benchmark.

```powershell
git clone https://github.com/danielronak/traceback.git
cd traceback
uv venv -p 3.14 .venv
.venv\Scripts\Activate.ps1
```

If PowerShell refuses to run `Activate.ps1`, run this once, then try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

PyTorch from the default package index is CPU-only on Windows, so install the
CUDA build. Run `nvidia-smi` and note the "CUDA Version" in the top right. On
[pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/)
choose Stable, Windows, Pip, Python and the newest CUDA version that isn't
above yours; it shows a `pip3 install ... --index-url ...` command. Run it as
`uv pip install` instead, for example:

```powershell
uv pip install torch --index-url https://download.pytorch.org/whl/cu128
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

That must print `True` and your RTX 3050. Then install the project and run its
tests, one suite at a time:

```powershell
uv pip install -e engine -e pipeline -e "training[dev]"
python -c "import torch; print(torch.cuda.is_available())"   # still True?
pytest engine
pytest pipeline
pytest training
```

If any test fails, stop and send me the output.

### 2. Make the prompts (a few minutes)

```powershell
python -m pymentor_pipeline generate
```

It writes about 85,000 prompts to `data\generated\v1\` (not committed).

### 3. Start the teacher

Install [Ollama for Windows](https://ollama.com/download); it runs in the
background. Then download the teacher, about 2.5 GB. Check the exact tag on
[ollama.com/library/qwen3](https://ollama.com/library/qwen3/tags): you want the
`4b-instruct-2507` model at `q4_K_M`.

```powershell
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama show qwen3:4b-instruct-2507-q4_K_M --license    # should be Apache 2.0
ollama run qwen3:4b-instruct-2507-q4_K_M "Say hello in five words."
ollama ps                                                # PROCESSOR should say 100% GPU
```

### 4. Trial run: 500 answers, then look at them (about 30 to 60 minutes)

```powershell
python -m pymentor_pipeline draft --url http://localhost:11434/v1/chat/completions `
  --model qwen3:4b-instruct-2507-q4_K_M --limit 500
python -m pymentor_pipeline review --sample 50
```

`draft` prints its progress every 100 answers: how many passed the grounding
and fix checks, and the seconds per answer. Rejected answers go to
`data\generated\v1\rejected-train.jsonl` with the reason. `review` then shows
50 accepted answers one at a time: press `y` if it's good teaching, `n` if
not (with a short note), `s` to skip and `q` to stop.

**Send me:** the last line `draft` printed, the first few rejections
(`Get-Content data\generated\v1\rejected-train.jsonl -TotalCount 5`) and the
review summary (`python -m pymentor_pipeline review --summary`). If the answers
look poor, I'll tune the teacher's instructions before the long run.

### 5. The full drafting run (overnight)

In Windows Settings, set the laptop never to sleep while plugged in, and keep
it plugged in and cool. Then:

```powershell
python -m pymentor_pipeline draft --url http://localhost:11434/v1/chat/completions `
  --model qwen3:4b-instruct-2507-q4_K_M --limit 15000
python -m pymentor_pipeline draft --url http://localhost:11434/v1/chat/completions `
  --model qwen3:4b-instruct-2507-q4_K_M --split val --limit 1500
```

Expect about 16,500 times the seconds per answer from step 4. `--limit` is
the total for that split, including the 500 from the trial, so if it stops,
run the same command again and it carries on where it left off.

### 6. Fine-tune the three tutors

Free the GPU first: `ollama stop qwen3:4b-instruct-2507-q4_K_M`, then check
`nvidia-smi` shows almost no memory in use. Each `train` downloads its base
model from Hugging Face the first time.

These settings are for 4 GB and are starting points that haven't run on a
real GPU yet. **Send me** the first lines each run prints (the memory estimate
and the first few losses), and the last line.

```powershell
# SmolLM2-135M: about 1.3 GB estimated, the quickest: do it first
python -m pymentor_training train --base HuggingFaceTB/SmolLM2-135M-Instruct `
  --data data/generated/v1 --out training/runs/smollm2-135m `
  --step-in-backward --grad-accum 1 --optimizer adafactor --gradient-checkpointing `
  --batch-size 8 --lr 5e-5 --epochs 3

# SmolLM2-360M: about 2.5 GB estimated
python -m pymentor_training train --base HuggingFaceTB/SmolLM2-360M-Instruct `
  --data data/generated/v1 --out training/runs/smollm2-360m `
  --step-in-backward --grad-accum 1 --optimizer adafactor --gradient-checkpointing `
  --batch-size 8 --lr 5e-5 --epochs 3

# Qwen2.5-Coder-0.5B: about 3.4 GB estimated, so close everything else first
python -m pymentor_training train --base Qwen/Qwen2.5-Coder-0.5B-Instruct `
  --data data/generated/v1 --out training/runs/qwen-coder-0.5b `
  --step-in-backward --grad-accum 1 --optimizer adafactor --gradient-checkpointing `
  --batch-size 2 --lr 3e-5 --epochs 3
```

`--step-in-backward` updates each weight as soon as its gradient is ready and
then frees it, so a full set of gradients never exists (D44). The batch you
set is then the whole batch. Add `--resume` to continue an interrupted run.
Out of memory ("CUDA out of memory")? Halve `--batch-size`, or lower
`--max-length` (1,024 by default; `train` reports how many examples were too
long and skipped). If Qwen still doesn't fit, `--dtype bf16` halves its
weights, at some risk that small updates round away.

### 7. Score, export, score again (for each tutor)

```powershell
python -m pymentor_training evaluate --model training/runs/smollm2-135m/best --name smollm2-135m-sft
python -m pymentor_training export --model training/runs/smollm2-135m/best --out training/runs/smollm2-135m/web
python -m pymentor_training evaluate --model training/runs/smollm2-135m/web `
  --onnx model_q4.onnx --name smollm2-135m-sft-q4
```

Repeat with `smollm2-360m` and `qwen-coder-0.5b`. Each `evaluate` prints one
summary line and writes its results to `benchmark\results\v0\`, next to the
template baseline. **Send me** the printed lines. To keep the results in the
repo, push them on a branch (the weights stay out; `.gitignore` excludes them):

```powershell
git checkout -b m6-results
git add benchmark/results/v0
git commit -m "benchmark: Track A results on v0"
git push -u origin m6-results
```

### On Linux instead

The same steps, with `source .venv/bin/activate`, `\` for line continuation,
and `uv pip install torch` (the default Linux build includes CUDA).

## Memory guide (4 GB)

`train` prints an estimate before it starts. With the settings above (fp32
weights, Adafactor, `--step-in-backward`), the weights take 4 bytes a
parameter, Adafactor's state a fraction of that, and gradients only the
largest single tensor (the vocabulary table):

| | Weights | Optimizer | Gradients | Plus | Estimate |
| --- | --- | --- | --- | --- | --- |
| SmolLM2-135M | 0.54 GB | ~0.05 GB | 0.11 GB | CUDA ~0.4 GB, activations | ~1.3 GB |
| SmolLM2-360M | 1.45 GB | ~0.15 GB | 0.19 GB | CUDA ~0.4 GB, activations | ~2.5 GB |
| Qwen2.5-Coder-0.5B | 1.98 GB | ~0.2 GB | 0.54 GB | CUDA ~0.4 GB, activations | ~3.4 GB |

Two things keep activations small: gradient checkpointing, and scoring the
vocabulary only at the answer's positions (`answer_loss`), which matters most
for Qwen's 152k vocabulary. Without `--step-in-backward`, add a full copy of
the weights for the gradients, which is too much for Qwen on 4 GB.
