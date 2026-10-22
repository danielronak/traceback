"""The course: its format, and a check of the real curriculum (also run inside
Pyodide by the app's CI)."""

import re
from pathlib import Path

import pytest

from pymentor import Engine
from pymentor.course import CourseError, Snippet, load_course, parse_course, parse_lesson
from pymentor.exercises import Exercise, parse_tests
from pymentor.selfcheck import check_course

CURRICULUM = Path(__file__).resolve().parents[2] / "curriculum"
COURSE = load_course(CURRICULUM)

LESSON = """+++
id = "demo"
title = "Demo"
teaches = ["missing-colon"]
+++

Some *Markdown*.

```python
print("hi")
```

More text.

```python broken=missing-colon inputs=a|b
if True
    pass
```
"""


def test_the_real_course_checks_out():
    assert check_course(Engine(step_limit=20_000), COURSE) == []


@pytest.mark.parametrize("lesson", COURSE.lessons.values(), ids=lambda lesson: lesson.id)
def test_lesson_file_name_matches_id(lesson):
    assert re.sub(r"^\d+-", "", Path(lesson.origin).stem) == lesson.id


def test_lessons_split_into_markdown_and_snippets():
    lesson = parse_lesson(LESSON, "demo.md")
    assert lesson.teaches == ("missing-colon",)
    assert [type(p).__name__ for p in lesson.parts] == ["str", "Snippet", "str", "Snippet"]
    assert lesson.parts[1] == Snippet('print("hi")\n')
    assert lesson.parts[3] == Snippet(
        "if True\n    pass\n", inputs=("a", "b"), broken="missing-colon"
    )
    assert lesson.to_dict()["parts"][0] == {"kind": "markdown", "text": "Some *Markdown*."}


@pytest.mark.parametrize(
    ("text", "complaint"),
    [
        ("# No front matter\n", "front matter"),
        ('+++\nid = "x"\ntitle = "X"\nlevel = 2\n+++\n', "unknown front matter"),
        ('+++\nid = "x"\ntitle = "X"\n+++\n```python run=fast\nx\n```\n', "unknown snippet option"),
    ],
)
def test_malformed_lessons_are_rejected(text, complaint):
    with pytest.raises(CourseError, match=complaint):
        parse_lesson(text, "x.md")


def _exercise(exercise_id):
    tests = parse_tests([{"output": "x"}], exercise_id)
    return Exercise(exercise_id, exercise_id.title(), "", "", "", tests)


@pytest.mark.parametrize(
    ("items", "complaint"),
    [
        ('["lesson:demo", "exercise:hello", "lesson:demo"]', "more than once"),
        ('["lesson:demo", "exercise:nope", "exercise:hello"]', "unknown exercise 'nope'"),
        ('["lesson:demo"]', "exercise 'hello' isn't in any unit"),
        ('["lesson:demo", "quiz:one", "exercise:hello"]', "lesson:id or exercise:id"),
    ],
)
def test_course_references_must_resolve_exactly_once(items, complaint):
    course = f'title = "T"\n[[unit]]\nid = "u"\ntitle = "U"\nitems = {items}\n'
    with pytest.raises(CourseError, match=complaint):
        parse_course(course, [parse_lesson(LESSON, "demo.md")], [_exercise("hello")])


def test_course_serialises_for_the_app():
    data = COURSE.to_dict()
    first = data["units"][0]["items"][0]
    assert first == {"kind": "lesson", "id": "printing", "title": "Showing things on screen"}
    assert data["lessons"]["printing"]["parts"][1]["kind"] == "code"
