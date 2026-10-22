"""Seed variants: the same program with its variables renamed.

Learners name things in endless ways, and a tutor that has only ever seen
`total` and `scores` would lean on the names instead of the code. A variant
renames every variable, parameter and function the program creates,
consistently, from a pool of plausible beginner names.

A variant belongs to its seed's group, so it lands in the same split (D16),
and it is kept only if the engine confirms it still passes the seed's tests
with no findings, exactly as the seed does.
"""

from __future__ import annotations

import ast
import builtins
import keyword
import random
import re
import tokenize
from dataclasses import replace

from pymentor import Engine
from pymentor.exercises import Exercise

from .corpus import Seed, expected_tests
from .mutate import Program

NAMES = (
    "amount", "answer", "average", "balance", "basket", "best", "bill", "box", "cart",
    "city", "colour", "count", "counter", "current", "data", "day", "days", "digit",
    "entry", "extra", "fee", "first", "friend", "fruit", "goal", "grade", "group",
    "guess", "height", "item", "items", "label", "last", "length", "letter", "level",
    "limit", "line", "lines", "marks", "message", "money", "month", "name", "names",
    "number", "numbers", "order", "part", "people", "person", "pet", "player", "points",
    "price", "prices", "rate", "record", "result", "results", "room", "row", "rows",
    "running", "score", "scores", "size", "speed", "step", "steps", "stock", "student",
    "students", "subject", "sum_so_far", "team", "temp", "text", "thing", "things", "tick",
    "total", "value", "values", "week", "weight", "width", "word", "words", "year",
    "my_list", "new_total", "the_name", "user_input", "how_many",
)  # fmt: skip
LETTERS = "abcijkmnpqtwxyz"
FUNCTION_NAMES = (
    "work_out", "get_total", "calculate", "find_answer", "make_list", "check", "show",
    "count_up", "add_up", "convert", "describe", "report", "handle", "process", "measure",
)  # fmt: skip
TAKEN = frozenset(dir(builtins)) | frozenset(keyword.kwlist) | frozenset(keyword.softkwlist)
IDENTIFIER = re.compile(r"[A-Za-z_]\w*")

_ENGINE: Engine | None = None


def rename(source: str, rng: random.Random, keep: frozenset[str] = frozenset()) -> str:
    """``source`` with each name it creates (other than ``keep``) renamed."""
    program = Program(source)
    tree = program.tree
    functions = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    # Names Python might see from outside the program's own code: attributes
    # (`pet.name`), keyword arguments (`print(end="")`), methods and classes.
    outside = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    outside |= {k.arg for n in ast.walk(tree) if isinstance(n, ast.Call) for k in n.keywords}
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        outside.add(cls.name)
        outside |= {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    names = sorted(
        n for n in program.user_names() - keep - outside if n[0].islower() and n not in TAKEN
    )

    used = set(program.names)
    mapping: dict[str, str] = {}
    for name in names:
        if name in functions:
            pool = FUNCTION_NAMES
        elif len(name) == 1:
            pool = LETTERS
        else:  # keep plurals plural: a list stays `prices`, a number stays `price`
            pool = tuple(n for n in NAMES if _plural(n) == _plural(name))
        free = [n for n in pool if n not in used]
        if not free:
            continue
        mapping[name] = rng.choice(free)
        used.add(mapping[name])

    lines = list(program.lines)
    previous = None
    edits = []
    for token in program.tokens:
        if (
            token.type == tokenize.NAME
            and token.string in mapping
            and (previous is None or previous.string != ".")
        ):
            edits.append(token)
        if token.type not in (tokenize.NL, tokenize.COMMENT):
            previous = token
    for token in reversed(edits):  # right to left keeps earlier columns valid
        row, col = token.start
        text = lines[row - 1]
        lines[row - 1] = text[:col] + mapping[token.string] + text[col + len(token.string) :]
    return "\n".join(lines) + "\n"


def _plural(name: str) -> bool:
    return name.endswith("s") and not name.endswith(("ss", "us", "is"))


def variants(seed: Seed, count: int) -> list[Seed]:
    """Up to ``count`` renamed copies of ``seed`` that still pass its tests cleanly."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = Engine()
    tests = expected_tests(seed)
    # Names the tests call (`double(4)`) must keep their names.
    keep = frozenset(IDENTIFIER.findall(" ".join(t.call or "" for t in tests)))
    exercise = Exercise(seed.id, seed.id, "", "", seed.source, tests)
    found: list[Seed] = []
    sources = {seed.source}
    for number in range(1, count + 1):
        source = rename(seed.source, random.Random(f"{seed.id}~{number}"), keep)
        if source in sources:
            continue
        report = _ENGINE.run_exercise(exercise, source)
        if report.passed and not report.findings:
            sources.add(source)
            found.append(replace(seed, id=f"{seed.id}~{number}", source=source, tests=tests))
    return found
