"""Renamed variants keep the program's meaning and only change its names."""

import random

from pymentor_pipeline.augment import rename, variants
from pymentor_pipeline.corpus import Seed
from pymentor_pipeline.generate import group_of

PROGRAM = """class Pet:
    def __init__(self, name):
        self.name = name


def describe(pet, times):
    words = []
    for i in range(times):
        words.append(pet.name)
    return " ".join(words)


rex = Pet("Rex")
print(describe(rex, 2), end="!\\n")
print(f"{rex.name} says hi")
"""


def test_rename_changes_names_consistently_and_keeps_what_python_sees():
    renamed = rename(PROGRAM, random.Random(1))
    assert renamed != PROGRAM
    # Attributes, methods, classes and keyword arguments are seen from outside.
    for kept in ("class Pet", "__init__", "self.name", ".append(", "end=", "pet.name"):
        assert kept.split(".")[-1] in renamed
    assert "rex" not in renamed and "words" not in renamed and "describe" not in renamed
    exec(compile(renamed, "<variant>", "exec"), {"__name__": "variant"})


def test_rename_keeps_names_the_tests_call():
    source = "def double(n):\n    answer = n * 2\n    return answer\n"
    renamed = rename(source, random.Random(3), keep=frozenset({"double"}))
    assert "def double(" in renamed and "answer" not in renamed


def test_variants_pass_the_seeds_tests_and_share_its_group():
    seed = Seed("program:999-pets", PROGRAM)
    found = variants(seed, 3)
    assert found
    assert len({v.source for v in found}) == len(found)
    for variant in found:
        assert variant.id.startswith("program:999-pets~")
        assert group_of(variant.id) == group_of(seed.id)


def test_a_program_with_nothing_to_rename_has_no_variants():
    assert variants(Seed("lesson:printing#1", 'print("Hello")\n'), 2) == []
