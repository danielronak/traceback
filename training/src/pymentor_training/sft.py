"""Supervised fine-tuning: a full fine-tune of a small open-weight model (M6).

    python -m pymentor_training train --base HuggingFaceTB/SmolLM2-360M-Instruct \\
        --data data/generated/v1 --out training/runs/smollm2-360m

It reads the accepted drafts (``drafts-train.jsonl``, ``drafts-val.jsonl``),
adds the prompt's section markers as special tokens, and trains on the targets
only. Built for a laptop GPU with 4 to 6 GB: weights can be kept in bf16, the
optimizer can be Adafactor (no per-weight momentum), and gradient
checkpointing trades compute for memory. ``memory_estimate`` says what fits
before anything is downloaded to the GPU.

Every run writes to its ``out`` folder: ``config.json``, ``log.jsonl`` (loss,
learning rate, throughput), ``last/`` (a resumable checkpoint), ``best/`` (the
lowest validation loss) and ``summary.json``. Interrupted runs continue with
``--resume``, from the same batch order.
"""

from __future__ import annotations

import json
import math
import random
import shutil
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup

from .data import add_special_tokens, collate, encode, load_drafts
from .infer import pick_device


@dataclass
class Config:
    base: str  # a Hugging Face model id, or a local folder
    data: str  # folder holding drafts-train.jsonl and drafts-val.jsonl
    out: str
    max_length: int = 1024
    batch_size: int = 8
    grad_accum: int = 4  # the effective batch is batch_size * grad_accum
    lr: float = 5e-5
    epochs: float = 3.0
    max_steps: int | None = None  # optimizer steps; overrides epochs
    warmup: float = 0.03  # share of the steps
    weight_decay: float = 0.0
    optimizer: str = "adamw"  # adamw, or adafactor for small GPUs
    # fp32 weights with mixed precision on a GPU (bf16, or fp16 with loss scaling
    # on older cards), or bf16 weights to save memory (updates can round away).
    dtype: str = "fp32"
    gradient_checkpointing: bool = False
    eval_every: int = 200
    save_every: int = 500
    seed: int = 0
    device: str = "auto"
    notes: dict[str, Any] = field(default_factory=dict)


def train(config: Config, *, resume: bool = False, log: Callable[[str], object] = print) -> dict:
    out = Path(config.out)
    out.mkdir(parents=True, exist_ok=True)
    device = pick_device(config.device)
    torch.manual_seed(config.seed)
    random.seed(config.seed)

    source = out / "last" if resume and (out / "last").exists() else config.base
    tokenizer = AutoTokenizer.from_pretrained(source)
    model = AutoModelForCausalLM.from_pretrained(source, **_load_dtype(config))
    add_special_tokens(tokenizer, model)
    if config.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        model.config.use_cache = False
    model.to(device)
    log(memory_estimate(model, config))

    train_set, dropped = _encode_all(tokenizer, Path(config.data) / "drafts-train.jsonl", config)
    val_set, _ = _encode_all(tokenizer, Path(config.data) / "drafts-val.jsonl", config)
    if not train_set:
        raise ValueError("no training examples fit max_length")
    batches_per_epoch = math.ceil(len(train_set) / config.batch_size)
    steps = config.max_steps or math.ceil(batches_per_epoch * config.epochs / config.grad_accum)
    log(
        f"{len(train_set)} training and {len(val_set)} validation examples "
        f"({dropped} too long for {config.max_length} tokens); {steps} optimizer steps on {device}"
    )

    optimizer = _optimizer(model, config)
    scheduler = get_cosine_schedule_with_warmup(optimizer, int(config.warmup * steps), steps)
    state = {"step": 0, "micro": 0, "best_val": None}
    if source != config.base:
        saved = torch.load(out / "last" / "trainer.pt", weights_only=False)
        optimizer.load_state_dict(saved["optimizer"])
        scheduler.load_state_dict(saved["scheduler"])
        state = saved["state"]
        log(f"resumed at step {state['step']}")
    else:
        (out / "config.json").write_text(json.dumps(asdict(config), indent=2) + "\n")

    autocast, scaler = _autocast(device, config)
    pad_id = tokenizer.pad_token_id
    model.train()
    started, tokens = time.monotonic(), 0
    while state["step"] < steps:
        epoch, index = divmod(state["micro"], batches_per_epoch)
        order = list(range(len(train_set)))
        random.Random(config.seed * 1000 + epoch).shuffle(order)
        chosen = order[index * config.batch_size : (index + 1) * config.batch_size]
        batch = {
            k: v.to(device) for k, v in collate([train_set[i] for i in chosen], pad_id).items()
        }
        with autocast:
            loss = model(**batch).loss / config.grad_accum
        scaler.scale(loss).backward()
        tokens += int(batch["attention_mask"].sum())
        state["micro"] += 1
        if state["micro"] % config.grad_accum:
            continue

        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()
        optimizer.zero_grad(set_to_none=True)
        state["step"] += 1
        step = state["step"]
        entry = {
            "step": step,
            "loss": round(loss.item() * config.grad_accum, 4),
            "lr": scheduler.get_last_lr()[0],
            "tokens_per_s": round(tokens / max(time.monotonic() - started, 1e-9)),
        }
        if step % config.eval_every == 0 or step == steps:
            entry["val_loss"] = evaluate_loss(model, val_set, pad_id, config, device, autocast)
            if entry["val_loss"] is not None and (
                state["best_val"] is None or entry["val_loss"] < state["best_val"]
            ):
                state["best_val"] = entry["val_loss"]
                _save(model, tokenizer, out / "best")
            model.train()
        _append(out / "log.jsonl", entry)
        if step % 20 == 0 or "val_loss" in entry:
            log(json.dumps(entry))
        if step % config.save_every == 0 or step == steps:
            _checkpoint(model, tokenizer, optimizer, scheduler, state, out / "last")

    if not (out / "best").exists():  # no validation set: the last weights are the result
        _save(model, tokenizer, out / "best")
    summary = {
        "steps": state["step"],
        "best_val_loss": state["best_val"],
        "train_examples": len(train_set),
        "val_examples": len(val_set),
        "parameters": sum(p.numel() for p in model.parameters()),
        "seconds": round(time.monotonic() - started, 1),
        "device": str(device),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


@torch.no_grad()
def evaluate_loss(model, examples, pad_id, config, device, autocast) -> float | None:
    """Mean loss per target token over a dataset."""
    if not examples:
        return None
    model.eval()
    total, count = 0.0, 0
    for start in range(0, len(examples), config.batch_size):
        batch = collate(examples[start : start + config.batch_size], pad_id)
        batch = {k: v.to(device) for k, v in batch.items()}
        targets = int((batch["labels"][:, 1:] != -100).sum())
        with autocast:
            total += model(**batch).loss.item() * targets
        count += targets
    return round(total / max(count, 1), 4)


def memory_estimate(model: Any, config: Config) -> str:
    """Rough GPU memory for weights, gradients and optimizer state (activations extra)."""
    n = sum(p.numel() for p in model.parameters())
    weight = 2 if config.dtype == "bf16" else 4
    optimizer = 0.1 * weight if config.optimizer == "adafactor" else 2 * weight
    gb = n * (weight * 2 + optimizer) / 1e9
    return (
        f"{n / 1e6:.0f}M parameters: about {gb:.1f} GB for weights, gradients and "
        f"{config.optimizer} state, plus activations"
    )


def _encode_all(tokenizer, path: Path, config: Config) -> tuple[list[dict], int]:
    if not path.exists():
        return [], 0
    encoded = [encode(tokenizer, e, config.max_length) for e in load_drafts(path)]
    kept = [e for e in encoded if e is not None]
    return kept, len(encoded) - len(kept)


def _load_dtype(config: Config) -> dict[str, Any]:
    # `dtype` is the current keyword; older transformers call it `torch_dtype`.
    dtype = torch.bfloat16 if config.dtype == "bf16" else torch.float32
    import transformers

    major = int(transformers.__version__.split(".")[0])
    return {"dtype": dtype} if major >= 5 else {"torch_dtype": dtype}


def _optimizer(model, config: Config) -> torch.optim.Optimizer:
    params = [p for p in model.parameters() if p.requires_grad]
    if config.optimizer == "adafactor":
        from transformers.optimization import Adafactor

        return Adafactor(
            params,
            lr=config.lr,
            weight_decay=config.weight_decay,
            scale_parameter=False,
            relative_step=False,
            warmup_init=False,
        )
    if config.optimizer != "adamw":
        raise ValueError(f"unknown optimizer {config.optimizer!r}")
    fused = next(model.parameters()).is_cuda
    return torch.optim.AdamW(params, lr=config.lr, weight_decay=config.weight_decay, fused=fused)


def _autocast(device: torch.device, config: Config):
    """The mixed-precision context and gradient scaler for this device.

    Ampere and newer GPUs (the RTX 3050 included) use bf16, which needs no
    scaling. Older ones, like the T4 in free cloud notebooks, use fp16 with a
    loss scaler. On the CPU, or with bf16 weights, everything is plain."""
    if device.type == "cuda" and config.dtype == "fp32":
        if torch.cuda.is_bf16_supported():
            return torch.autocast("cuda", dtype=torch.bfloat16), torch.amp.GradScaler(enabled=False)
        return torch.autocast("cuda", dtype=torch.float16), torch.amp.GradScaler("cuda")
    return torch.autocast(device.type, enabled=False), torch.amp.GradScaler(enabled=False)


def _save(model, tokenizer, folder: Path) -> None:
    tmp = folder.with_name(folder.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    model.save_pretrained(tmp)
    tokenizer.save_pretrained(tmp)
    shutil.rmtree(folder, ignore_errors=True)
    tmp.rename(folder)  # a crash mid-save never leaves a half-written folder


def _checkpoint(model, tokenizer, optimizer, scheduler, state, folder: Path) -> None:
    _save(model, tokenizer, folder)
    torch.save(
        {"optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(), "state": state},
        folder / "trainer.pt",
    )


def _append(path: Path, entry: dict) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry) + "\n")
