"""Validates the curriculum: every exercise's reference solution passes cleanly
and its starter compiles, fails, and gets taught by a rule card; every lesson
snippet runs cleanly or shows the mistake it names; and the course outline
places every lesson and exercise exactly once."""

import re
from pathlib import Path

import pytest

from pymentor import Engine
from pymentor.course import load_course
from pymentor.selfcheck import check_exercise, check_lesson

CURRICULUM = Path(__file__).resolve().parents[2] / "curriculum"
COURSE = load_course(CURRICULUM)  # also checks the outline
EXERCISES = list(COURSE.exercises.values())
LESSONS = list(COURSE.lessons.values())
ENGINE = Engine(step_limit=50_000)


def test_there_are_seed_exercises():
    assert len(EXERCISES) >= 15


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e.id)
def test_file_name_matches_id(exercise):
    assert re.sub(r"^\d+-", "", Path(exercise.origin).stem) == exercise.id


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda e: e.id)
def test_solution_passes_and_starter_is_taught(exercise):
    assert check_exercise(ENGINE, exercise) == []


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda lesson: lesson.id)
def test_lesson_file_name_matches_id(lesson):
    assert re.sub(r"^\d+-", "", Path(lesson.origin).stem) == lesson.id


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda lesson: lesson.id)
def test_lesson_snippets_run_as_described(lesson):
    assert lesson.snippets, "a lesson needs at least one runnable snippet"
    assert check_lesson(ENGINE, lesson) == []
