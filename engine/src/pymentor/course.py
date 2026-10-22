"""The course: units of lessons and exercises, in the order a learner meets them.

``curriculum/course.toml`` lists units, each an ordered list of items such as
``"lesson:printing"`` or ``"exercise:hello-world"``. Lessons are Markdown files
in ``curriculum/lessons/`` that start with TOML front matter between ``+++``
lines::

    +++
    id = "printing"
    title = "Showing things on screen"
    teaches = ["print-statement", "unterminated-string"]   # rule-card ids
    +++

Fenced ``python`` blocks in a lesson are snippets the learner can run. The
fence's info string can say more::

    ```python inputs=Ada|14          (answers for input(), separated by |)
    ```python broken=missing-colon   (a deliberate mistake, taught by that card)

``selfcheck.check_course`` runs every snippet: ordinary ones must run cleanly,
and broken ones must be taught by exactly the card they name.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exercises import Exercise, load_exercises

LESSON_FIELDS = {"id", "title", "teaches"}
ITEM = re.compile(r"^(lesson|exercise):([a-z0-9]+(?:-[a-z0-9]+)*)$")
FENCE = re.compile(
    r"^```python(?P<info>[^\n]*)\n(?P<code>.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL
)


class CourseError(ValueError):
    """The course or a lesson is malformed. Raised at load time."""


@dataclass(frozen=True)
class Snippet:
    code: str
    inputs: tuple[str, ...] = ()
    broken: str | None = None  # the card that should teach this deliberate mistake

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "code",
            "code": self.code,
            "inputs": list(self.inputs),
            "broken": self.broken,
        }


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    teaches: tuple[str, ...]
    parts: tuple[str | Snippet, ...]  # Markdown text and snippets, in order
    origin: str = ""

    @property
    def snippets(self) -> list[Snippet]:
        return [p for p in self.parts if isinstance(p, Snippet)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "teaches": list(self.teaches),
            "parts": [
                p.to_dict() if isinstance(p, Snippet) else {"kind": "markdown", "text": p}
                for p in self.parts
            ],
        }


@dataclass(frozen=True)
class Unit:
    id: str
    title: str
    items: tuple[tuple[str, str], ...]  # (kind, id) pairs


@dataclass(frozen=True)
class Course:
    title: str
    units: tuple[Unit, ...]
    lessons: dict[str, Lesson]
    exercises: dict[str, Exercise]

    def to_dict(self) -> dict[str, Any]:
        def title(kind: str, item_id: str) -> str:
            return (self.lessons if kind == "lesson" else self.exercises)[item_id].title

        return {
            "title": self.title,
            "units": [
                {
                    "id": unit.id,
                    "title": unit.title,
                    "items": [{"kind": k, "id": i, "title": title(k, i)} for k, i in unit.items],
                }
                for unit in self.units
            ],
            "lessons": {lesson_id: lesson.to_dict() for lesson_id, lesson in self.lessons.items()},
        }


# --- lessons -------------------------------------------------------------------


def parse_lesson(text: str, origin: str) -> Lesson:
    match = re.match(r"\A\+\+\+\n(.*?)^\+\+\+[ \t]*\n", text, re.MULTILINE | re.DOTALL)
    if not match:
        raise CourseError(f"{origin}: a lesson starts with TOML front matter between +++ lines")
    try:
        meta = tomllib.loads(match[1])
    except tomllib.TOMLDecodeError as error:
        raise CourseError(f"{origin}: invalid front matter: {error}") from error
    if unknown := set(meta) - LESSON_FIELDS:
        raise CourseError(f"{origin}: unknown front matter fields {sorted(unknown)}")
    for key in ("id", "title"):
        if not isinstance(meta.get(key), str):
            raise CourseError(f"{origin}: '{key}' must be a string")
    teaches = meta.get("teaches", [])
    if not isinstance(teaches, list) or not all(isinstance(t, str) for t in teaches):
        raise CourseError(f"{origin}: 'teaches' must be a list of rule-card ids")
    return Lesson(
        id=meta["id"],
        title=meta["title"],
        teaches=tuple(teaches),
        parts=_split(text[match.end() :], origin),
        origin=origin,
    )


def _split(body: str, origin: str) -> tuple[str | Snippet, ...]:
    parts: list[str | Snippet] = []
    position = 0
    for fence in FENCE.finditer(body):
        if text := body[position : fence.start()].strip():
            parts.append(text)
        parts.append(_snippet(fence["info"], fence["code"], origin))
        position = fence.end()
    if text := body[position:].strip():
        parts.append(text)
    return tuple(parts)


def _snippet(info: str, code: str, origin: str) -> Snippet:
    inputs: tuple[str, ...] = ()
    broken = None
    for option in info.split():
        key, _, value = option.partition("=")
        if key == "inputs" and value:
            inputs = tuple(value.split("|"))
        elif key == "broken" and value:
            broken = value
        else:
            raise CourseError(
                f"{origin}: unknown snippet option '{option}' (use inputs= or broken=)"
            )
    return Snippet(code=code, inputs=inputs, broken=broken)


# --- the course ------------------------------------------------------------------


def parse_course(
    course_text: str,
    lessons: list[Lesson],
    exercises: list[Exercise],
    origin: str = "course.toml",
) -> Course:
    try:
        data = tomllib.loads(course_text)
    except tomllib.TOMLDecodeError as error:
        raise CourseError(f"{origin}: invalid TOML: {error}") from error
    if set(data) - {"title", "unit"} or not isinstance(data.get("title"), str):
        raise CourseError(f"{origin}: needs a 'title' and [[unit]] tables, nothing else")
    by_kind = {
        "lesson": _unique({lesson.id: lesson for lesson in lessons}, lessons, "lesson"),
        "exercise": _unique({e.id: e for e in exercises}, exercises, "exercise"),
    }
    units = []
    placed: set[str] = set()
    for entry in data.get("unit", []):
        if set(entry) != {"id", "title", "items"}:
            raise CourseError(f"{origin}: each unit has exactly 'id', 'title' and 'items'")
        items = []
        for item in entry["items"]:
            match = ITEM.match(item)
            if not match:
                raise CourseError(f"{origin}: '{item}' should look like lesson:id or exercise:id")
            if match[2] not in by_kind[match[1]]:
                raise CourseError(
                    f"{origin}: unit '{entry['id']}' lists unknown {match[1]} '{match[2]}'"
                )
            if item in placed:
                raise CourseError(f"{origin}: '{item}' appears more than once")
            placed.add(item)
            items.append((match[1], match[2]))
        units.append(Unit(entry["id"], entry["title"], tuple(items)))
    for kind, known in by_kind.items():
        for item_id in known:
            if f"{kind}:{item_id}" not in placed:
                raise CourseError(f"{origin}: {kind} '{item_id}' isn't in any unit")
    return Course(data["title"], tuple(units), by_kind["lesson"], by_kind["exercise"])


def load_course(root: Path) -> Course:
    """The course in a curriculum folder: course.toml, lessons/ and exercises/."""
    root = Path(root)
    lessons = [
        parse_lesson(path.read_text(encoding="utf-8"), str(path))
        for path in sorted((root / "lessons").glob("*.md"))
    ]
    return parse_course(
        (root / "course.toml").read_text(encoding="utf-8"),
        lessons,
        load_exercises(root / "exercises"),
        str(root / "course.toml"),
    )


def _unique(by_id: dict[str, Any], items: list[Any], kind: str) -> dict[str, Any]:
    if len(by_id) != len(items):
        raise CourseError(f"two {kind}s share an id")
    return by_id
