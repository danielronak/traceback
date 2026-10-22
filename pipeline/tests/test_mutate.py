"""Each mutator injects the mistake it names, and the engine teaches it with
the card that mistake should get. (The engine decides; these tests check the
mutators produce realistic input for it.)"""

import pytest

from pymentor import Engine
from pymentor.exercises import Exercise, ExerciseTest
from pymentor_pipeline.mutate import MUTATORS, Program, mutate, typo

ENGINE = Engine(step_limit=20_000)

PROGRAM = """import math


def describe(radius):
    area = math.pi * radius ** 2
    return f"Area: {area:.1f}"


sizes = [1, 2, 3]
for size in range(len(sizes)):
    if sizes[size] == 2:
        print("Two")
    print(describe(sizes[size]))
"""

EXPECTED = {
    "drop_colon": "missing-colon",
    "assign_in_condition": "assign-in-condition",
    "dedent_body": "indent-expected",
    "extra_indent": "unexpected-indent",
    "unclose_bracket": "bracket-never-closed",
    "extra_bracket": "bracket-unmatched",
    "mismatch_bracket": "bracket-mismatch",
    "unterminate_string": "unterminated-string",
    "misspell_keyword": "keyword-typo",
    "dedent_return": "return-outside-function",
    "misspell_name": "name-typo",
    "misspell_builtin": "builtin-typo",
    "unquote_string": "name-meant-string",
    "drop_import": "missing-import",
    "capitalise_variable": "naming-variable",
    "off_by_one": "index-out-of-range",
    "print_instead_of_return": "wrong-output",  # print(describe(...)) now prints None
    "drop_f_prefix": "wrong-output",
}


def first_card(source):
    expected_output = ENGINE.run(PROGRAM).stdout
    exercise = Exercise("t", "T", "", "", PROGRAM, (ExerciseTest(output=expected_output),))
    findings = ENGINE.run_exercise(exercise, source).findings
    return findings[0].card.id if findings and findings[0].card else None


@pytest.mark.parametrize(("kind", "card"), EXPECTED.items())
def test_mutator_produces_the_mistake_its_card_teaches(kind, card):
    mutations = [m for m in mutate(PROGRAM, per_kind=50) if m.kind == kind]
    assert mutations, f"{kind} found nowhere to apply"
    assert card in {first_card(m.source) for m in mutations}


def test_every_mutator_is_covered_or_known_not_to_apply():
    # These need shapes this program doesn't have; the corpus covers them.
    elsewhere = {"python2_print", "def_without_brackets", "drop_conversion", "compare_flip"}
    assert set(MUTATORS) == set(EXPECTED) | elsewhere


def test_mutations_are_deterministic_and_capped():
    first = mutate(PROGRAM, per_kind=2, seed="x")
    assert first == mutate(PROGRAM, per_kind=2, seed="x")
    kinds = [m.kind for m in first]
    assert max(kinds.count(k) for k in set(kinds)) <= 2


def test_mutations_change_exactly_what_they_say():
    for mutation in mutate(PROGRAM, per_kind=50):
        assert mutation.source != PROGRAM
        assert 1 <= mutation.line <= len(PROGRAM.splitlines())


def test_typos_are_plausible():
    import random

    rng = random.Random(0)
    for word in ["total", "print", "while", "if"]:
        wrong = typo(word, rng)
        assert wrong != word and abs(len(wrong) - len(word)) <= 1


def test_program_knows_its_own_names():
    assert Program(PROGRAM).user_names() >= {"describe", "radius", "area", "sizes", "size"}
