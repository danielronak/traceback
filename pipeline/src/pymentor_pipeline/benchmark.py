"""Benchmark v0: held-out cases, frozen.

The benchmark answers "is a model better than the card template, and is it
grounded?" (D12). Its cases come from three places, none of them seen in
training (D16):

- **Mutations of test-split seeds**, sampled evenly across cards so the common
  syntax mistakes don't drown out the rest.
- **Card examples**: the hand-written minimal programs every card carries.
  They are never seeds, so no training example comes from them.
- **Course mistakes in test-split groups**: exercise starters and lessons'
  deliberately broken snippets.

Each case stores the engine's finding as it was when the benchmark was built,
so later engine changes can't silently move the goalposts. A built version is
never modified (CLAUDE.md); a better benchmark is a new version.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pymentor import Engine, prompt
from pymentor.course import load_course
from pymentor.exercises import Exercise

from .corpus import load_seeds
from .generate import TIMED_OUT, analyse, make_jobs, run_jobs, split_of, test_to_dict
from .records import finding_from_record, finding_to_record

VERSION = "v0"
TARGET_CASES = 300
# Error messages change between Python versions, so a benchmark is built on the
# Python the app ships (D15): Pyodide 314 is Python 3.14 (D25).
PYTHON = (3, 14)


def build(repo: Path, *, log: Callable[[str], object] = print) -> list[dict[str, Any]]:
    """Every benchmark case, in a stable order."""
    if sys.version_info[:2] != PYTHON:
        raise RuntimeError(
            f"build benchmarks on Python {'.'.join(map(str, PYTHON))}, as the app ships"
        )
    engine = Engine()
    hand = _card_examples(engine) + _course_mistakes(engine, repo)
    mutations = _mutation_cases(repo)
    log(f"{len(hand)} hand-written cases, {len(mutations)} held-out mutations to sample from")
    cases = hand + _sample_evenly(mutations, TARGET_CASES - len(hand))
    seen: set[str] = set()
    unique = []
    for case in cases:
        key = prompt.build(finding_from_record(case["finding"]), case["source"], "explain")
        if key not in seen:
            seen.add(key)
            unique.append(case)
    return sorted(unique, key=lambda c: c["id"])


def write(cases: list[dict[str, Any]], folder: Path) -> str:
    """Write a version's files; refuses to touch a version that exists."""
    if (folder / "cases.jsonl").exists():
        raise FileExistsError(f"{folder} is frozen; build a new version instead")
    folder.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n" for c in cases)
    (folder / "cases.jsonl").write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode()).hexdigest()
    (folder / "SHA256SUMS").write_text(f"{digest}  cases.jsonl\n", encoding="utf-8")
    return digest


def load(folder: Path) -> list[dict[str, Any]]:
    with (folder / "cases.jsonl").open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def _case(
    case_id: str, origin: str, source: str, inputs, tests, finding, **extra
) -> dict[str, Any]:
    return {
        "id": case_id,
        "origin": origin,
        "source": source,
        "inputs": list(inputs),
        "tests": [test_to_dict(t) for t in tests],
        "finding": finding_to_record(finding),
        **extra,
    }


def _card_examples(engine: Engine) -> list[dict[str, Any]]:
    cases = []
    for card in engine.cards:
        for number, example in enumerate(card.examples, start=1):
            if example.tests:
                exercise = Exercise("example", "Example", "", "", "", example.tests)
                findings = engine.run_exercise(exercise, example.source).findings
            else:
                findings = engine.run(example.source, list(example.inputs)).findings
            finding = next(f for f in findings if f.card and f.card.id == card.id)
            cases.append(
                _case(
                    f"card-{card.id}-{number}",
                    "card-example",
                    example.source,
                    example.inputs,
                    example.tests,
                    finding,
                )
            )
    return cases


def _course_mistakes(engine: Engine, repo: Path) -> list[dict[str, Any]]:
    course = load_course(repo / "curriculum")
    cases = []
    for exercise in course.exercises.values():
        if split_of(f"exercise:{exercise.id}") != "test":
            continue
        findings = engine.run_exercise(exercise, exercise.starter).findings
        if findings and findings[0].card:
            cases.append(
                _case(
                    f"starter-{exercise.id}",
                    "exercise-starter",
                    exercise.starter,
                    (),
                    exercise.tests,
                    findings[0],
                )
            )
    for lesson in course.lessons.values():
        if split_of(f"lesson:{lesson.id}") != "test":
            continue
        for number, snippet in enumerate(lesson.snippets, start=1):
            if snippet.broken is None:
                continue
            findings = engine.run(snippet.code, list(snippet.inputs)).findings
            if findings and findings[0].card:
                cases.append(
                    _case(
                        f"lesson-{lesson.id}-{number}",
                        "lesson-mistake",
                        snippet.code,
                        snippet.inputs,
                        (),
                        findings[0],
                    )
                )
    return cases


def _mutation_cases(repo: Path) -> list[dict[str, Any]]:
    seeds = [s for s in load_seeds(repo) if split_of(s.id) == "test"]
    jobs = make_jobs(seeds, per_kind=12)
    cases = []
    for job, record in run_jobs(jobs, analyse):
        if record is TIMED_OUT or record is None or record["card"] is None:
            continue
        digest = hashlib.sha256(job.source.encode()).hexdigest()[:12]
        cases.append(
            {
                "id": f"mutation-{digest}",
                "origin": "mutation",
                "seed": job.seed,
                "kind": job.kind,
                "source": job.source,
                "inputs": [],
                "tests": list(job.tests),
                "finding": record,
            }
        )
    return sorted(cases, key=lambda c: c["id"])


def _sample_evenly(cases: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """Up to ``count`` cases, taking one per card in turn so rare cards count."""
    by_card: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_card[case["finding"]["card"]["id"]].append(case)
    rng = random.Random(VERSION)
    for group in by_card.values():
        rng.shuffle(group)
    chosen: list[dict[str, Any]] = []
    while len(chosen) < count and any(by_card.values()):
        for card in sorted(by_card):
            if by_card[card] and len(chosen) < count:
                chosen.append(by_card[card].pop())
    return chosen
