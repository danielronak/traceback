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


def report(data: Path, split: str, *, per_reason: int = 3, show: Callable[[str], object] = print):
    """A drafting checkpoint in one go: counts, rejection reasons with examples,
    one accepted answer per task, and the human review so far."""

    def rows(name: str) -> list[dict[str, Any]]:
        path = data / f"{name}-{split}.jsonl"
        return read_jsonl(path) if path.exists() else []

    accepted, rejected = rows("drafts"), rows("rejected")
    show(f"ACCEPTED {len(accepted)}, REJECTED {len(rejected)}")
    show(f"accepted by task: {dict(Counter(r['task'] for r in accepted))}")
    show(f"rejected by task: {dict(Counter(r['task'] for r in rejected))}")
    reasons = Counter(x.split(":")[0] for r in rejected for x in r["reasons"])
    show(f"rejection reasons: {reasons.most_common()}")
    show(f"review so far: {summary(data, split)}")
    grades = rows("grades")
    if grades:
        from .grade import summary as grade_summary

        show(f"grader: {grade_summary(grades)}")
    targets = {(r["case"], r["task"]): r["target"] for r in accepted}
    for verdict in rows("reviews"):
        if verdict["verdict"] == "bad":
            show(f"\n=== REVIEWED BAD {verdict['task']}: {verdict['note'] or '(no note)'}")
            answer = targets.get((verdict["case"], verdict["task"]), "")
            show(f">>> {answer.removesuffix('<|end|>')}")
    graded_bad = [g for g in grades if g["verdict"] != "good"]
    for verdict in graded_bad[: per_reason * 2]:
        show(f"\n=== GRADED {verdict['verdict'].upper()} {verdict['task']}: {verdict['reason']}")
        answer = targets.get((verdict["case"], verdict["task"]), "")
        show(f">>> {answer.removesuffix('<|end|>')}")
    for reason, _ in reasons.most_common():
        examples = [r for r in rejected if any(x.startswith(reason) for x in r["reasons"])]
        for row in examples[:per_reason]:
            show(f"\n=== REJECTED ({reason}) {row['task']}: {row['reasons']}")
            show(f">>> {row['output']}")
    seen: set[str] = set()
    for row in accepted:
        if row["task"] in seen:
            continue
        seen.add(row["task"])
        lines = row["prompt"].splitlines()
        error = next((line for line in lines if line.startswith("<|error|>")), "")
        code = row["prompt"].split("<|code|>", 1)[1].removesuffix("<|response|>").strip()
        show(f"\n=== ACCEPTED {row['task']} | {error.removeprefix('<|error|>')}")
        show(code)
        show(f">>> {row['target'].removesuffix('<|end|>')}")
