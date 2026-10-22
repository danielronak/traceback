"""The lesson and course formats: parsing, snippet options and outline checks."""

import pytest

from pymentor import Engine
from pymentor.course import CourseError, Lesson, parse_course, parse_lesson
from pymentor.exercises import Exercise
from pymentor.selfcheck import check_lesson

ENGINE = Engine(step_limit=50_000)

LESSON = """\
+++
id = "demo"
title = "A demo"
+++
Some text.

```python
print("hi")
```

```text
not run
```

```python mistake=name-typo input="Ada Lovelace" input=3
message = "Hi"
print(mesage)
```
"""


def lesson(body: str) -> Lesson:
    return parse_lesson(f'+++\nid = "x"\ntitle = "X"\n+++\n{body}', "x.md")


def test_lesson_front_matter_and_body():
    parsed = parse_lesson(LESSON, "demo.md")
    assert (parsed.id, parsed.title) == ("demo", "A demo")
    assert parsed.body.startswith("Some text.")
    assert "+++" not in parsed.body


def test_only_python_blocks_are_snippets_with_their_options():
    first, second = parse_lesson(LESSON, "demo.md").snippets
    assert first.source == 'print("hi")\n'
    assert first.line == 8  # the code's first line in the file
    assert (first.mistake, first.inputs) == (None, ())
    assert second.mistake == "name-typo"
    assert second.inputs == ("Ada Lovelace", "3")
    assert second.line == 16


def test_longer_fences_can_hold_shorter_ones():
    (snippet,) = lesson('````python\ns = """\n```\n"""\n````\n').snippets
    assert snippet.source == 's = """\n```\n"""\n'


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("no front matter\n", "front matter"),
        ('+++\nid = "x"\n+++\n', "'title' must be a string"),
        ('+++\nid = "x"\ntitle = "X"\nlevel = 1\n+++\n', "unknown fields"),
        ('+++\nid = "x"\ntitle = "X"\n+++\n```python\nprint(1)\n', "never closed"),
        ('+++\nid = "x"\ntitle = "X"\n+++\n```python run\nprint(1)\n```\n', "unknown snippet"),
    ],
)
def test_malformed_lessons_are_rejected(text, message):
    with pytest.raises(CourseError, match=message):
        parse_lesson(text, "x.md")


def test_check_lesson_accepts_clean_and_intended_mistakes():
    assert check_lesson(ENGINE, parse_lesson(LESSON, "demo.md")) == []


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        ("```python\nUserName = 1\nprint(UserName)\n```\n", "snippet has findings"),
        ("```python mistake=missing-colon\nprint(1)\n```\n", "should show missing-colon"),
        ("```python mistake=no-such-card\nprint(1)\n```\n", "no card"),
        ("```python\nprint(input())\n```\n", "input-exhausted"),
    ],
)
def test_check_lesson_reports_bad_snippets(body, problem):
    (reported,) = check_lesson(ENGINE, lesson(body))
    assert problem in reported


# --- the course outline --------------------------------------------------------


def exercise(exercise_id: str) -> Exercise:
    return Exercise(exercise_id, exercise_id, "", "", "", ())


LESSONS = [lesson("Text.\n")]
EXERCISES = [exercise("e1"), exercise("e2")]
OUTLINE = """\
title = "Course"
[[unit]]
id = "u1"
title = "Unit one"
steps = [{ lesson = "x" }, { exercise = "e1" }]
[[unit]]
id = "u2"
title = "Unit two"
steps = [{ exercise = "e2" }]
"""


def test_course_orders_steps_into_units():
    course = parse_course(OUTLINE, "course.toml", LESSONS, EXERCISES)
    assert [u.id for u in course.units] == ["u1", "u2"]
    assert [(s.kind, s.id) for s in course.steps] == [
        ("lesson", "x"),
        ("exercise", "e1"),
        ("exercise", "e2"),
    ]
    assert course.to_dict()["units"][0]["steps"][1] == {"kind": "exercise", "id": "e1"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (('{ exercise = "e2" }', '{ exercise = "e3" }'), "no exercise with id 'e3'"),
        (('{ exercise = "e2" }', '{ exercise = "e1" }'), "already in the course"),
        (('{ exercise = "e2" }', '{ quiz = "e2" }'), "a step is"),
        (('id = "u2"', 'id = "u1"'), "duplicate unit id"),
        (('steps = [{ exercise = "e2" }]', "steps = []"), "at least one step"),
        (('[{ lesson = "x" }, ', "["), r"lessons aren't in the course: \[.x.\]"),
    ],
)
def test_malformed_courses_are_rejected(change, message):
    with pytest.raises(CourseError, match=message):
        parse_course(OUTLINE.replace(*change), "course.toml", LESSONS, EXERCISES)
