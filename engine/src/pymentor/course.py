"""The course: lessons and exercises, ordered into units.

A **lesson** is a Markdown file with TOML front matter between ``+++`` lines::

    +++
    id = "printing"
    title = "Showing things on the screen"
    +++
    Text, then a runnable snippet:

    ```python
    print("Hello")
    ```

Every ``python`` code block is a runnable snippet. Its info string may carry
options, written like shell words:

- ``mistake=CARD-ID``: the snippet shows a mistake on purpose, and that card
  must be its first finding. Without it, a snippet must run with no findings at
  all, since learners copy what lessons show.
- ``input=VALUE``: a line typed at an ``input()`` prompt. Repeat it for more
  lines, and quote values with spaces: ``input="Ada Lovelace"``.

Use ``text`` or another language for code that isn't meant to run.

The **course** file (``course.toml``) orders lessons and exercises into units::

    title = "Python from zero"
    [[unit]]
    id = "first-steps"
    title = "First steps"
    steps = [{ lesson = "printing" }, { exercise = "hello-world" }]

Every lesson and exercise must appear in the course exactly once.
"""

from __future__ import annotations

import re
import shlex
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exercises import Exercise, load_exercises

LESSON_FIELDS = {"id", "title"}
COURSE_FIELDS = {"title", "unit"}
UNIT_FIELDS = {"id", "title", "steps"}
SNIPPET_OPTIONS = {"mistake", "input"}
STEP_KINDS = ("lesson", "exercise")

_FRONT_MATTER = re.compile(r"\A\+\+\+\n(.*?)\n\+\+\+\n", re.DOTALL)
_FENCE = re.compile(r"^(`{3,})([^`\n]*)$")


class CourseError(ValueError):
    """A lesson or the course file is malformed. Raised at load time."""


@dataclass(frozen=True)
class Snippet:
    source: str
    line: int  # where the code starts in the lesson file, 1-based
    mistake: str | None = None  # the card this snippet shows on purpose
    inputs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "line": self.line,
            "mistake": self.mistake,
            "inputs": list(self.inputs),
        }


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    body: str  # Markdown, front matter removed, snippets left in place
    snippets: tuple[Snippet, ...] = ()
    origin: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "snippets": [s.to_dict() for s in self.snippets],
        }


@dataclass(frozen=True)
class Step:
    kind: str  # "lesson" or "exercise"
    id: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "id": self.id}


@dataclass(frozen=True)
class Unit:
    id: str
    title: str
    steps: tuple[Step, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "steps": [s.to_dict() for s in self.steps]}


@dataclass(frozen=True)
class Course:
    title: str
    units: tuple[Unit, ...]
    lessons: dict[str, Lesson] = field(default_factory=dict)
    exercises: dict[str, Exercise] = field(default_factory=dict)

    @property
    def steps(self) -> list[Step]:
        """Every step, in course order."""
        return [step for unit in self.units for step in unit.steps]

    def to_dict(self) -> dict[str, Any]:
        """The outline only. Lessons and exercises are sent separately."""
        return {"title": self.title, "units": [u.to_dict() for u in self.units]}


# --- lessons -----------------------------------------------------------------------


def parse_lesson(text: str, origin: str) -> Lesson:
    text = text.replace("\r\n", "\n")
    match = _FRONT_MATTER.match(text)
    if match is None:
        raise CourseError(f"{origin}: a lesson starts with front matter between '+++' lines")
    try:
        data = tomllib.loads(match.group(1))
    except tomllib.TOMLDecodeError as error:
        raise CourseError(f"{origin}: invalid front matter: {error}") from error
    if unknown := set(data) - LESSON_FIELDS:
        raise CourseError(f"{origin}: unknown fields {sorted(unknown)}")
    for key in ("id", "title"):
        if not isinstance(data.get(key), str):
            raise CourseError(f"{origin}: '{key}' must be a string")
    first_line = match.group(0).count("\n") + 1
    body = text[match.end() :]
    return Lesson(
        id=data["id"],
        title=data["title"],
        body=body,
        snippets=_snippets(body, first_line, origin),
        origin=origin,
    )


def _snippets(body: str, first_line: int, origin: str) -> tuple[Snippet, ...]:
    snippets = []
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        opening = _FENCE.match(lines[i])
        if opening is None:
            i += 1
            continue
        fence, info = opening.group(1), opening.group(2).strip()
        start = i + 1
        end = next((j for j in range(start, len(lines)) if lines[j].strip() == fence), None)
        where = f"{origin}:{first_line + i}"
        if end is None:
            raise CourseError(f"{where}: code block is never closed")
        words = shlex.split(info) if info else []
        if words and words[0] == "python":
            source = "\n".join(lines[start:end]) + "\n"
            snippets.append(_snippet(source, first_line + start, words[1:], where))
        i = end + 1
    return tuple(snippets)


def _snippet(source: str, line: int, options: list[str], where: str) -> Snippet:
    mistake = None
    inputs = []
    for option in options:
        key, equals, value = option.partition("=")
        if not equals or key not in SNIPPET_OPTIONS:
            raise CourseError(
                f"{where}: unknown snippet option '{option}' "
                f"(expected {', '.join(f'{k}=...' for k in sorted(SNIPPET_OPTIONS))})"
            )
        if key == "mistake":
            mistake = value
        else:
            inputs.append(value)
    return Snippet(source=source, line=line, mistake=mistake, inputs=tuple(inputs))


def load_lessons(folder: Path) -> list[Lesson]:
    """Every ``*.md`` lesson under a folder, in path order."""
    lessons = [
        parse_lesson(path.read_text(encoding="utf-8"), str(path))
        for path in sorted(Path(folder).rglob("*.md"))
    ]
    seen: set[str] = set()
    for lesson in lessons:
        if lesson.id in seen:
            raise CourseError(f"{lesson.origin}: duplicate lesson id '{lesson.id}'")
        seen.add(lesson.id)
    return lessons


# --- the course --------------------------------------------------------------------


def parse_course(
    text: str, origin: str, lessons: list[Lesson], exercises: list[Exercise]
) -> Course:
    """The course outline, checked against the lessons and exercises it orders."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise CourseError(f"{origin}: invalid TOML: {error}") from error
    if unknown := set(data) - COURSE_FIELDS:
        raise CourseError(f"{origin}: unknown fields {sorted(unknown)}")
    if not isinstance(data.get("title"), str):
        raise CourseError(f"{origin}: 'title' must be a string")
    raw_units = data.get("unit")
    if not isinstance(raw_units, list) or not raw_units:
        raise CourseError(f"{origin}: add at least one [[unit]]")

    by_kind = {
        "lesson": {lesson.id: lesson for lesson in lessons},
        "exercise": {exercise.id: exercise for exercise in exercises},
    }
    units = []
    placed: set[tuple[str, str]] = set()
    for n, raw in enumerate(raw_units, 1):
        where = f"{origin}: unit {n}"
        if not isinstance(raw, dict):
            raise CourseError(f"{where}: must be a table")
        if unknown := set(raw) - UNIT_FIELDS:
            raise CourseError(f"{where}: unknown fields {sorted(unknown)}")
        for key in ("id", "title"):
            if not isinstance(raw.get(key), str):
                raise CourseError(f"{where}: '{key}' must be a string")
        if raw["id"] in {u.id for u in units}:
            raise CourseError(f"{where}: duplicate unit id '{raw['id']}'")
        steps = []
        for raw_step in raw.get("steps", []):
            step = _step(raw_step, f"{origin}: unit '{raw['id']}'")
            if step.id not in by_kind[step.kind]:
                raise CourseError(f"{where}: no {step.kind} with id '{step.id}'")
            if (step.kind, step.id) in placed:
                raise CourseError(f"{where}: {step.kind} '{step.id}' is already in the course")
            placed.add((step.kind, step.id))
            steps.append(step)
        if not steps:
            raise CourseError(f"{where}: a unit needs at least one step")
        units.append(Unit(id=raw["id"], title=raw["title"], steps=tuple(steps)))

    for kind, items in by_kind.items():
        if missing := sorted(i for i in items if (kind, i) not in placed):
            raise CourseError(f"{origin}: these {kind}s aren't in the course: {missing}")
    return Course(
        title=data["title"],
        units=tuple(units),
        lessons=by_kind["lesson"],
        exercises=by_kind["exercise"],
    )


def _step(raw: Any, where: str) -> Step:
    if not isinstance(raw, dict) or len(raw) != 1 or next(iter(raw)) not in STEP_KINDS:
        raise CourseError(f'{where}: a step is {{ lesson = "id" }} or {{ exercise = "id" }}')
    kind, step_id = next(iter(raw.items()))
    if not isinstance(step_id, str):
        raise CourseError(f"{where}: a step's id must be a string")
    return Step(kind=kind, id=step_id)


def load_course(folder: Path) -> Course:
    """``course.toml``, ``lessons/`` and ``exercises/`` under a curriculum folder."""
    folder = Path(folder)
    path = folder / "course.toml"
    return parse_course(
        path.read_text(encoding="utf-8"),
        str(path),
        load_lessons(folder / "lessons"),
        load_exercises(folder / "exercises"),
    )
