"""Validates every exercise in curriculum/: the reference solution passes cleanly,
and the starter compiles, fails, and gets taught by a rule card."""

import re
from pathlib import Path

import pytest

from pymentor import Engine
from pymentor.exercises import load_exercises
from pymentor.selfcheck import check_exercise

FOLDER = Path(__file__).resolve().parents[2] / "curriculum" / "exercises"
EXERCISES = load_exercises(FOLDER)
ENGINE = Engine(step_limit=50_000)


def test_there_are_seed_exercises():
    assert len(EXERCISES) >= 15


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e.id)
def test_file_name_matches_id(exercise):
    assert re.sub(r"^\d+-", "", Path(exercise.origin).stem) == exercise.id


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e.id)
def test_solution_passes_and_starter_is_taught(exercise):
    assert check_exercise(ENGINE, exercise) == []
