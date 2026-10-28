"""Training examples: drafted targets, tokenised the way inference will see them.

A training example is a prompt built by ``pymentor.prompt`` (D10) and the
target a teacher drafted for it (``pipeline/draft.py``), which ends with
``<|end|>``. The prompt's section markers become special tokens, so the
tokenizer never splits them, and the loss counts only the target: the model
learns to answer, not to repeat the facts it was given.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from pymentor import prompt

END = "<|end|>"
IGNORE = -100  # label for tokens the loss skips


@dataclass(frozen=True)
class Example:
    case: str
    task: str
    prompt: str
    target: str  # ends with <|end|>


def load_drafts(path: Path) -> list[Example]:
    """Accepted drafts (``drafts-<split>.jsonl``) as training examples, minus any
    the grader marked bad (``grades-<split>.jsonl``, if it exists; D50)."""
    path = Path(path)
    bad = {(r["case"], r["task"]) for r in _rows(_grades_for(path)) if r["verdict"] == "bad"}
    return [
        Example(r["case"], r["task"], r["prompt"], r["target"])
        for r in _rows(path)
        if (r["case"], r["task"]) not in bad
    ]


def _grades_for(drafts: Path) -> Path:
    return drafts.with_name(drafts.name.replace("drafts-", "grades-", 1))


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def add_special_tokens(tokenizer: Any, model: Any = None) -> int:
    """Add the prompt's section markers as special tokens, never split, plus a
    pad token if there is none, and grow the model's embeddings to match (new
    rows start near the mean of the old ones). Returns how many were new."""
    added = tokenizer.add_tokens(list(prompt.SPECIAL_TOKENS), special_tokens=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or END
    if model is not None and len(tokenizer) > model.get_input_embeddings().weight.shape[0]:
        model.resize_token_embeddings(len(tokenizer), mean_resizing=True)
    return added


def prompt_ids(tokenizer: Any, text: str) -> list[int]:
    """Token ids for a prompt, exactly as training and inference both see it."""
    return tokenizer(text, add_special_tokens=False)["input_ids"]


def encode(tokenizer: Any, example: Example, max_length: int) -> dict[str, list[int]] | None:
    """Ids and labels for one example, or None if it doesn't fit ``max_length``."""
    head = prompt_ids(tokenizer, example.prompt)
    tail = tokenizer(example.target, add_special_tokens=False)["input_ids"]
    if len(head) + len(tail) > max_length:
        return None
    return {"input_ids": head + tail, "labels": [IGNORE] * len(head) + tail}


def collate(batch: list[dict[str, list[int]]], pad_id: int) -> dict[str, torch.Tensor]:
    """Right-pad a batch. Padding is masked out of attention and the loss."""
    width = max(len(b["input_ids"]) for b in batch)
    ids, labels, mask = [], [], []
    for b in batch:
        gap = width - len(b["input_ids"])
        ids.append(b["input_ids"] + [pad_id] * gap)
        labels.append(b["labels"] + [IGNORE] * gap)
        mask.append([1] * len(b["input_ids"]) + [0] * gap)
    return {
        "input_ids": torch.tensor(ids),
        "labels": torch.tensor(labels),
        "attention_mask": torch.tensor(mask),
    }
