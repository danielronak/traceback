"""Seed programs: correct beginner code for the mutators to break.

Seeds come from three places, all written for this project:

- ``pipeline/corpus/programs/*.py``: standalone programs. A first-line
  comment such as ``# inputs: Ada | 14`` gives answers for ``input()``.
- The course's exercises: each reference solution, with the exercise's tests.
- The course's lessons: every runnable (not deliberately broken) snippet.

A seed without tests gets one derived from itself (``expected_tests``): its
own printed output for its inputs. A mutation that changes that output
without crashing is a logic error, taught by the logic cards.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pymentor.course import load_course
from pymentor.exercises import ExerciseTest
from pymentor.sandbox import execute

INPUTS = re.compile(r"\A# inputs: (.*)\n")
LICENCE = "Written for PyMentor; licensed with the repository"


@dataclass(frozen=True)
class Seed:
    id: str  # "program:012-shopping-list", "exercise:double", "lesson:printing#2"
    source: str
    inputs: tuple[str, ...] = ()
    tests: tuple[ExerciseTest, ...] = ()
    origin: str = ""
    licence: str = LICENCE


def load_programs(folder: Path) -> list[Seed]:
    seeds = []
    for path in sorted(Path(folder).glob("*.py")):
        source = path.read_text(encoding="utf-8")
        match = INPUTS.match(source)
        inputs = tuple(part.strip() for part in match[1].split("|")) if match else ()
        seeds.append(Seed(f"program:{path.stem}", source, inputs, origin=str(path)))
    return seeds


def load_curriculum(root: Path) -> list[Seed]:
    course = load_course(root)
    seeds = [
        Seed(f"exercise:{e.id}", e.solution, tests=e.tests, origin=e.origin)
        for e in course.exercises.values()
    ]
    for lesson in course.lessons.values():
        for number, snippet in enumerate(lesson.snippets, start=1):
            if snippet.broken is None:
                seeds.append(
                    Seed(f"lesson:{lesson.id}#{number}", snippet.code, snippet.inputs, origin=lesson.origin)
                )
    return seeds


def load_seeds(repo: Path) -> list[Seed]:
    """Every seed, in a stable order."""
    repo = Path(repo)
    return load_programs(repo / "pipeline" / "corpus" / "programs") + load_curriculum(repo / "curriculum")


def expected_tests(seed: Seed, step_limit: int = 200_000) -> tuple[ExerciseTest, ...]:
    """The seed's own tests, or one made from what it prints for its inputs."""
    if seed.tests:
        return seed.tests
    result = execute(seed.source, list(seed.inputs), step_limit=step_limit)
    return (ExerciseTest(inputs=seed.inputs, output=result.printed),)
