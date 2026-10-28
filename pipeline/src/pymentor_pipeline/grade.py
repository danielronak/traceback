"""Automatic review: a local model grades drafted answers the way a person would.

Grounding catches wrong facts it can see, such as line numbers, names and code.
It can't tell whether a claim about what the code *does* is true, or whether a
hint says too much. A person can, but reading 50 answers per trial is slow.
``grade`` asks a local model to judge every accepted draft against a rubric
that mirrors the human review, and writes ``grades-<split>.jsonl``.

A grader is only useful if it agrees with people, so ``calibrate`` first grades
answers that people already reviewed (earlier trials' ``reviews-*.jsonl``) and
reports how often it agrees. Graders run locally, like teachers (D40).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .draft import Teacher
from .generate import read_jsonl

RUBRIC = """You check answers that a Python tutor wrote for absolute beginners. You get the \
facts the tutor was given (the task, the error Python reported, the rule card, sometimes a \
hint, a verified fix or the learner's question, and the learner's code with line numbers), \
then the tutor's answer.

The answer is BAD if any of these is true:
1. It says something untrue about the learner's code: what a line contains, what a value \
is, what the code does, or why it fails. Check every claim against the code and the error.
2. It is wrong for its task:
   - hint_level_1 says what is wrong, what is missing or what to change, or explains the \
rule. It should only point to where to look and ask a question.
   - hint_level_2 names the exact symbol, word or code that fixes the error, or says no \
more than pointing at the line.
   - hint_level_3 doesn't say exactly what to change.
   - explain doesn't say what Python objected to, and why, in terms of the learner's code.
   - why_followup doesn't answer the learner's question, or doesn't connect the reason to \
their code.
3. Its advice wouldn't work for this code.
4. It would confuse a beginner.

Otherwise it is GOOD. Reply with one line only: GOOD, or BAD: and a reason in a few words."""

Grader = Teacher  # (system, prompt) -> text: the same local model servers


def grade_one(grader: Grader, prompt_text: str, answer: str) -> tuple[str, str]:
    """``("good" | "bad" | "unclear", reason)`` for one drafted answer."""
    facts = prompt_text.removesuffix("<|response|>").strip()
    reply = grader(RUBRIC, f"{facts}\n\nThe tutor's answer:\n{answer.removesuffix('<|end|>')}")
    line = (reply or "").strip().splitlines()[0].strip() if (reply or "").strip() else ""
    word = line.split(":", 1)[0].strip(" *.").upper()
    if word == "GOOD":
        return "good", ""
    if word == "BAD":
        return "bad", line.split(":", 1)[1].strip() if ":" in line else ""
    return "unclear", line


def grade(
    data: Path,
    split: str,
    grader: Grader,
    *,
    name: str,
    log: Callable[[str], object] = print,
) -> dict[str, Any]:
    """Grade every accepted draft not yet graded; returns the summary."""
    path = data / f"grades-{split}.jsonl"
    done = {_key(r) for r in (read_jsonl(path) if path.exists() else [])}
    todo = [d for d in read_jsonl(data / f"drafts-{split}.jsonl") if _key(d) not in done]
    for number, row in enumerate(todo, start=1):
        verdict, reason = grade_one(grader, row["prompt"], row["target"])
        entry = {"case": row["case"], "task": row["task"], "verdict": verdict}
        _append(path, entry | {"reason": reason, "grader": name})
        if number % 100 == 0:
            log(f"  graded {number}/{len(todo)}")
    return summary(read_jsonl(path))


def summary(grades: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(grades)
    by_task: dict[str, Counter[str]] = {}
    for r in rows:
        by_task.setdefault(r["task"], Counter())[r["verdict"]] += 1
    return {
        "graded": len(rows),
        "good": _share(sum(r["verdict"] == "good" for r in rows), len(rows)),
        "by_task": {t: dict(c) for t, c in sorted(by_task.items())},
    }


def calibrate(folders: Iterable[Path], grader: Grader, *, split: str = "train") -> dict[str, Any]:
    """Grade answers people already reviewed, and compare the verdicts."""
    pairs = []  # (human, grader) verdicts
    for folder in folders:
        drafts = {_key(d): d for d in read_jsonl(folder / f"drafts-{split}.jsonl")}
        for review in read_jsonl(folder / f"reviews-{split}.jsonl"):
            row = drafts.get(_key(review))
            if review["verdict"] == "skip" or row is None:
                continue
            verdict, _ = grade_one(grader, row["prompt"], row["target"])
            pairs.append((review["verdict"], "good" if verdict == "good" else "bad"))
    bad_by_people = [g for h, g in pairs if h == "bad"]
    bad_by_grader = [h for h, g in pairs if g == "bad"]
    return {
        "answers": len(pairs),
        "agreement": _share(sum(h == g for h, g in pairs), len(pairs)),
        # Of the answers people marked bad, how many the grader caught.
        "catches_bad": _share(bad_by_people.count("bad"), len(bad_by_people)),
        # Of the answers the grader marked bad, how many people agreed were bad.
        "bad_is_right": _share(bad_by_grader.count("bad"), len(bad_by_grader)),
        "good_by_people": _share(sum(h == "good" for h, _ in pairs), len(pairs)),
        "good_by_grader": _share(sum(g == "good" for _, g in pairs), len(pairs)),
    }


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return row["case"], row["task"]


def _append(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")
