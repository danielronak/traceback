"""A small spot-check tool for drafted targets.

Grounding catches wrong facts, not bad teaching. Before training on a batch of
drafts, a person reads a sample: is it clear, kind, correct, and right for
its task? ``review`` shows drafts one at a time and records each verdict in
``reviews-<split>.jsonl``; ``summary`` gives the acceptance rate, which the
model card should report.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .generate import read_jsonl

VERDICTS = {"y": "good", "n": "bad", "s": "skip"}


def review(
    data: Path,
    split: str,
    *,
    sample: int = 50,
    seed: int = 0,
    ask: Callable[[str], str] = input,
    show: Callable[[str], object] = print,
) -> Counter[str]:
    """Show a random sample of drafts not yet reviewed, and record verdicts."""
    path = data / f"reviews-{split}.jsonl"
    seen = {(r["case"], r["task"]) for r in (read_jsonl(path) if path.exists() else [])}
    drafts = [d for d in read_jsonl(data / f"drafts-{split}.jsonl") if _key(d) not in seen]
    random.Random(seed).shuffle(drafts)
    tally: Counter[str] = Counter()
    for number, row in enumerate(drafts[:sample], start=1):
        show(f"\n--- {number}/{min(sample, len(drafts))}  {row['case']}  {row['task']}")
        show(row["prompt"].split("<|code|>", 1)[0].strip())
        show("<|code|>" + row["prompt"].split("<|code|>", 1)[1].removesuffix("<|response|>"))
        show(f">>> {row['target'].removesuffix('<|end|>')}")
        answer = ""
        while answer not in VERDICTS and answer != "q":
            answer = ask("good? [y]es / [n]o / [s]kip / [q]uit: ").strip().lower()[:1]
        if answer == "q":
            break
        note = ask("note (optional): ").strip() if answer == "n" else ""
        verdict = VERDICTS[answer]
        tally[verdict] += 1
        with path.open("a", encoding="utf-8", newline="\n") as file:
            entry = {"case": row["case"], "task": row["task"], "verdict": verdict, "note": note}
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return tally


def summary(data: Path, split: str) -> dict[str, Any]:
    path = data / f"reviews-{split}.jsonl"
    rows = read_jsonl(path) if path.exists() else []
    judged = [r for r in rows if r["verdict"] != "skip"]
    by_task: dict[str, Counter[str]] = {}
    for r in judged:
        by_task.setdefault(r["task"], Counter())[r["verdict"]] += 1
    good = sum(r["verdict"] == "good" for r in judged)
    return {
        "reviewed": len(judged),
        "good": round(good / len(judged), 3) if judged else None,
        "by_task": {t: dict(c) for t, c in sorted(by_task.items())},
    }


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return row["case"], row["task"]
