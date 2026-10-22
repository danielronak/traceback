"""Validates every exercise in curriculum/: the reference solution passes cleanly,
and the starter compiles, fails, and gets taught by a rule card."""

import re
from pathlib import Path

import pytest

from pymentor import Engine
from pymentor.exercises import load_exercises

FOLDER = Path(__file__).resolve().parents[2] / "curriculum" / "exercises"
EXERCISES = load_exercises(FOLDER)
ENGINE = Engine(step_limit=50_000)


def test_there_are_seed_exercises():
    assert len(EXERCISES) >= 15


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e.id)
def test_file_name_matches_id(exercise):
    assert re.sub(r"^\d+-", "", Path(exercise.origin).stem) == exercise.id


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e.id)
def test_solution_passes_with_no_findings(exercise):
    report = ENGINE.run_exercise(exercise, exercise.solution)
    failed = [r.test.to_dict() for r in report.results if not r.passed]
    assert report.passed, f"solution fails: {failed}"
    # Solutions are what learners compare against, so they must be exemplary.
    assert [f.diagnostic.code for f in report.findings] == []


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e.id)
def test_starter_compiles_fails_and_is_taught(exercise):
    report = ENGINE.run_exercise(exercise, exercise.starter)
    assert not any(f.diagnostic.severity.value == "syntax" for f in report.findings)
    assert not report.passed, "the starter already passes every test"
    first = report.findings[0]
    assert first.card is not None, (
        f"no card for {first.diagnostic.code}: {first.diagnostic.message}"
    )
