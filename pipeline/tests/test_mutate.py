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


# Mutators that need a shape PROGRAM doesn't have get a program of their own.
SHOP = """prices = {"tea": 2, "cake": 3}
basket = ["tea", "cake"]


def line_cost(item, count):
    cost = prices[item] * count
    return cost


total = 0
for item in basket:
    total = total + line_cost(item, 2)
basket.sort()
print("Total:", total)
print(f"Items: {len(basket)}")
print(prices["cake"])
"""
COUNTDOWN = """count = 3
while count > 0:
    print(count)
    count -= 1
word = "go"
print(word.upper())
for i in range(2):
    print(i)
"""
OWN_PROGRAM = {
    "drop_comma": (SHOP, "missing-comma"),
    "half_dedent": (SHOP, "unindent-mismatch"),
    "tab_indent": (SHOP, "tabs-and-spaces"),
    "reverse_assignment": (SHOP, "assign-to-non-name"),
    "square_bracket_call": (SHOP, "brackets-for-call"),
    "drop_argument": (SHOP, "missing-argument"),
    "extra_argument": (SHOP, "too-many-arguments"),
    "drop_return": (SHOP, "none-in-calculation"),
    "assign_inplace_result": (SHOP + "basket.append('jam')\n", "none-from-inplace-method"),
    "misspell_key": (SHOP, "key-missing"),
    "swap_lines": (SHOP, "used-before-assignment"),
    "concatenate_number": (SHOP, "str-plus-int"),
    "python2_print": (SHOP, "print-statement"),
    "drop_conversion": ("# inputs: 4\nn = int(input())\nprint(n + 1)\n", "input-is-string"),
    "compare_flip": (COUNTDOWN, "wrong-output"),
    "drop_increment": (COUNTDOWN, "loop-condition-unchanged"),
    "misspell_method": (COUNTDOWN, "attribute-typo"),
    "for_over_number": (COUNTDOWN, "int-not-iterable"),
    "def_without_brackets": (
        "def greet():\n    print('hi')\n\n\ngreet()\n",
        "def-missing-brackets",
    ),
}


def first_card(source, program=PROGRAM):
    inputs = ["4"] if "input(" in program else []
    expected_output = ENGINE.run(program, inputs).stdout
    test = ExerciseTest(inputs=tuple(inputs), output=expected_output)
    exercise = Exercise("t", "T", "", "", program, (test,))
    findings = ENGINE.run_exercise(exercise, source).findings
    return findings[0].card.id if findings and findings[0].card else None


@pytest.mark.parametrize(("kind", "card"), EXPECTED.items())
def test_mutator_produces_the_mistake_its_card_teaches(kind, card):
    mutations = [m for m in mutate(PROGRAM, per_kind=50) if m.kind == kind]
    assert mutations, f"{kind} found nowhere to apply"
    assert card in {first_card(m.source) for m in mutations}


@pytest.mark.parametrize(("kind", "case"), OWN_PROGRAM.items())
def test_mutator_on_its_own_program(kind, case):
    program, card = case
    mutations = [m for m in mutate(program, per_kind=50) if m.kind == kind]
    assert mutations, f"{kind} found nowhere to apply"
    assert card in {first_card(m.source, program) for m in mutations}


def test_every_mutator_is_covered():
    assert set(MUTATORS) <= set(EXPECTED) | set(OWN_PROGRAM)


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
