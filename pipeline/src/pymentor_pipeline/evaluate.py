"""The evaluation harness: score any model on a benchmark version.

A *model* is any callable that takes an ``Item`` and returns its text. Real
models should read only ``item.prompt``, exactly what they'd see in the app;
the template baseline (D12) reads the card instead, since it has no language
of its own.

Automatic scores, per task and overall:

- **grounded**: the share of outputs ``pymentor.grounding`` accepts, and which
  checks the rest failed (line, name, code, error-type, leak, length, empty).
- **words**: mean length, and the share over the task's limit.
- **fix**: of outputs containing a code block, the share whose code the engine
  verifies as a fix: put in place of the broken line(s), it removes this error
  without a new one at or before its line (the same test the app's fixes pass).
- **latency**: median and 95th percentile milliseconds per output.

Clarity and hint quality need people, so ``hand_sheet`` exports a sample to a
CSV for scoring by hand.
"""

from __future__ import annotations

import csv
import importlib
import json
import re
import statistics
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pymentor import grounding, prompt
from pymentor.exercises import Exercise, evaluate_tests, parse_tests
from pymentor.facts import Finding
from pymentor.fixes import verify
from pymentor.sandbox import execute

from .records import finding_from_record

FENCE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class Item:
    """One thing a model is asked to write."""

    case: str
    task: str
    prompt: str
    finding: Finding
    source: str
    inputs: tuple[str, ...]
    tests: tuple[dict[str, Any], ...]


Model = Callable[[Item], str]


def items(cases: Iterable[dict[str, Any]]) -> list[Item]:
    found = []
    for case in cases:
        finding = finding_from_record(case["finding"])
        for task in prompt.tasks_for(finding):
            found.append(
                Item(
                    case["id"],
                    task,
                    prompt.build(finding, case["source"], task),
                    finding,
                    case["source"],
                    tuple(case.get("inputs", ())),
                    tuple(case.get("tests", ())),
                )
            )
    return found


def run_model(model: Model, todo: list[Item]) -> list[dict[str, Any]]:
    """The model's output for every item, timed."""
    outputs = []
    for item in todo:
        started = time.perf_counter()
        text = model(item)
        latency = (time.perf_counter() - started) * 1000
        outputs.append({"case": item.case, "task": item.task, "output": text, "ms": latency})
    return outputs


def score(todo: list[Item], outputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Automatic scores for outputs (from ``run_model``, or a JSONL file of them)."""
    by_key = {(o["case"], o["task"]): o for o in outputs}
    rows = []
    for item in todo:
        output = by_key.get((item.case, item.task))
        text = output["output"] if output else ""
        problems = grounding.check(text, item.finding, item.source, item.task)
        block = FENCE.search(text)
        rows.append(
            {
                "task": item.task,
                "grounded": not problems,
                "problems": sorted({p.check for p in problems}),
                "words": len(text.split()),
                "over_limit": any(p.check == "length" for p in problems),
                "has_code": block is not None,
                "fix_ok": block is not None and fix_verifies(item, block[1]),
                "ms": output.get("ms") if output else None,
                "missing": output is None,
            }
        )
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[row["task"]].append(row)
    return {
        "items": len(rows),
        "overall": _summary(rows),
        "tasks": {task: _summary(group) for task, group in sorted(by_task.items())},
    }


def fix_verifies(item: Item, code: str) -> bool:
    """Does the model's code, put in place of the broken line(s), fix this error?"""
    d = item.finding.diagnostic
    fix = item.finding.fix
    lines = item.source.splitlines()
    start = fix.line if fix else d.line
    # A fix with nothing before it (`import math` added at the top) inserts lines.
    count = len(fix.before.splitlines()) if fix else 1
    new = code.rstrip("\n").splitlines()
    if not new:
        return False
    if len(new) > max(count, 1) and len(new) >= len(lines) - 1:
        candidates = ["\n".join(new) + "\n"]  # a whole program
    else:
        versions = [new]
        indent = re.match(r"\s*", lines[start - 1])[0] if start <= len(lines) else ""
        if indent and new[0] == new[0].lstrip():
            # Copied without its indentation, or the fix *is* removing it: try both.
            versions.append([indent + text if text.strip() else text for text in new])
        candidates = [
            "\n".join(lines[: start - 1] + v + lines[start - 1 + count :]) + "\n" for v in versions
        ]
    recheck = None
    if item.tests:
        exercise = Exercise(
            item.case, item.case, "", "", "", parse_tests(list(item.tests), item.case)
        )

        def recheck(source: str):
            return evaluate_tests(exercise, source)[1]

    for fixed in candidates:
        try:
            if verify(d, fixed, execute, list(item.inputs), recheck):
                return True
        except (SyntaxError, ValueError):
            continue
    return False


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    with_code = [r for r in rows if r["has_code"]]
    times = sorted(r["ms"] for r in rows if r["ms"] is not None)
    problems = Counter(p for r in rows for p in r["problems"])
    return {
        "n": n,
        "grounded": _share(sum(r["grounded"] for r in rows), n),
        "problems": dict(problems.most_common()),
        "mean_words": round(statistics.fmean(r["words"] for r in rows), 1) if rows else 0,
        "over_limit": _share(sum(r["over_limit"] for r in rows), n),
        "with_code": len(with_code),
        "fix_ok": _share(sum(r["fix_ok"] for r in with_code), len(with_code)),
        "ms_p50": round(statistics.median(times), 2) if times else None,
        "ms_p95": round(times[int(0.95 * (len(times) - 1))], 2) if times else None,
        "missing": sum(r["missing"] for r in rows),
    }


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def hand_sheet(
    todo: list[Item], outputs: list[dict[str, Any]], path: Path, *, per_task: int = 12
) -> int:
    """A CSV of a sample of outputs, with empty columns for people to score."""
    by_key = {(o["case"], o["task"]): o["output"] for o in outputs}
    by_task: dict[str, list[Item]] = defaultdict(list)
    for item in todo:
        by_task[item.task].append(item)
    chosen = []
    for task in sorted(by_task):
        group = by_task[task]
        step = max(1, len(group) // per_task)
        chosen.extend(group[::step][:per_task])
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(
            [
                "case",
                "task",
                "card",
                "error",
                "code",
                "output",
                "clarity_1_to_5",
                "hint_quality_1_to_5",
                "accurate_y_n",
                "notes",
            ]
        )
        for item in chosen:
            d = item.finding.diagnostic
            writer.writerow(
                [
                    item.case,
                    item.task,
                    item.finding.card.id if item.finding.card else "",
                    f"{d.code} line {d.line}: {d.message}",
                    prompt.format_window(prompt.code_window(item.source, d.line)),
                    by_key.get((item.case, item.task), ""),
                    "",
                    "",
                    "",
                    "",
                ]
            )
    return len(chosen)


def save_results(
    todo: list[Item],
    outputs: list[dict[str, Any]],
    name: str,
    version: str,
    benchmarks: Path,
    extra: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    """Score outputs and write ``results/<version>/<name>``: the report, the
    outputs and the hand-scoring sheet. Returns the report and the sheet's rows."""
    report = score(todo, outputs) | {"model": name, "benchmark": version} | (extra or {})
    folder = benchmarks / "results" / version
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    with (folder / f"{name}-outputs.jsonl").open("w", encoding="utf-8", newline="\n") as file:
        for output in outputs:
            file.write(json.dumps({**output, "ms": round(output.get("ms") or 0, 3)}) + "\n")
    rows = hand_sheet(todo, outputs, folder / f"{name}-hand-scoring.csv")
    return report, rows


def load_model(spec: str) -> Model:
    """``template``, or ``package.module:function`` for any other model."""
    if spec == "template":
        from .baseline import template

        return template
    module, _, name = spec.partition(":")
    return getattr(importlib.import_module(module), name)


def read_outputs(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]
