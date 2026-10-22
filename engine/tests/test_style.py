import ast
import builtins

import pytest

from pymentor.style import SHADOWED_BUILTINS, check_style, to_cap_words, to_snake_case


def codes(source):
    return [(d.code, d.line) for d in check_style(ast.parse(source))]


def test_flags_non_snake_case_variables_once_per_name():
    assert codes("Total = 1\nTotal = 2\nmyAge = 3\n") == [
        ("naming-variable", 1),
        ("naming-variable", 3),
    ]


def test_allows_snake_case_constants_and_dunders():
    assert codes("total_score = 1\nMAX_SIZE = 10\nN = 3\n_private = 1\n") == []
    assert codes("class Dog:\n    def __init__(self):\n        pass\n") == []


def test_function_and_class_names():
    found = check_style(ast.parse("def CalcTotal():\n    pass\nclass dog:\n    pass\n"))
    assert [(d.code, d.data["suggested_name"], d.col, d.end_col) for d in found] == [
        ("naming-function", "calc_total", 4, 13),
        ("naming-class", "Dog", 6, 9),
    ]


def test_shadowed_builtins():
    assert codes("list = [1]\nsum = 0\nid = 3\n") == [
        ("builtin-shadowed", 1),
        ("builtin-shadowed", 2),
    ]


def test_comparisons():
    assert codes("x = None\nif x == None:\n    pass\nif x != True:\n    pass\n") == [
        ("compare-none", 2),
        ("compare-bool", 4),
    ]
    assert codes("x = 1\nif x is None or x == 0:\n    pass\n") == []


@pytest.mark.parametrize(
    ("name", "snake"),
    [("Total", "total"), ("myTotal", "my_total"), ("HTTPCode", "http_code"), ("_Value", "_value")],
)
def test_to_snake_case(name, snake):
    assert to_snake_case(name) == snake


def test_to_cap_words():
    assert [to_cap_words(n) for n in ("dog", "my_dog", "myDog")] == ["Dog", "MyDog", "MyDog"]


def test_shadowed_builtins_are_real_builtins():
    assert set(dir(builtins)) >= SHADOWED_BUILTINS
