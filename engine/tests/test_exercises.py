import pytest

from pymentor import Engine, Severity
from pymentor.exercises import (
    Exercise,
    ExerciseError,
    _same_value,
    evaluate_tests,
    parse_exercise,
    parse_tests,
)

ENGINE = Engine(step_limit=20_000)


def exercise(*tests, **fields):
    return Exercise("demo", "Demo", "", "", "", parse_tests(list(tests), "demo"), **fields)


@pytest.mark.parametrize(
    ("tests", "complaint"),
    [
        ([], "at least one test"),
        ([{"call": "f()"}], "needs 'expect'"),
        ([{"call": "f()", "expect": "8", "output": "8"}], "either 'call'"),
        ([{"call": "f(", "expect": "8"}], "must be Python"),
        ([{"call": "f()", "expect": "len(x)"}], "must be Python"),
        ([{"output": "8", "inputs": [3]}], "list of strings"),
        ([{"output": "8", "colour": "red"}], "unknown fields"),
    ],
)
def test_malformed_tests_are_rejected(tests, complaint):
    with pytest.raises(ExerciseError, match=complaint):
        parse_tests(tests, "demo")


def test_exercise_files_need_their_fields():
    with pytest.raises(ExerciseError, match="'starter' must be a string"):
        parse_exercise('id = "x"\ntitle = "X"\nprompt = ""\nsolution = ""\n', "x.toml")


@pytest.mark.parametrize(
    ("actual", "expected", "same"),
    [
        (8, 8, True),
        (3.0, 3, True),
        (0.1 + 0.2, 0.3, True),
        (1, True, False),  # True == 1 in Python, but a test asking for True means a bool
        ("8", 8, False),
        ([1, 3], [1, 3], True),
    ],
)
def test_value_comparison(actual, expected, same):
    assert _same_value(actual, expected) is same


def test_output_tests_ignore_prompts_and_trailing_whitespace():
    demo = exercise({"inputs": ["Ada"], "output": "Hello, Ada!\n\n"})
    source = 'name = input("Name? ")\nprint("Hello, " + name + "!   ")\n'
    assert ENGINE.run_exercise(demo, source).passed


def test_only_the_first_failure_becomes_a_finding_but_all_results_are_kept():
    demo = exercise({"call": "double(1)", "expect": "2"}, {"call": "double(5)", "expect": "10"})
    report = ENGINE.run_exercise(demo, "def double(n):\n    return n + 2\n")
    assert [r.passed for r in report.results] == [False, False]
    [finding] = report.findings
    assert finding.diagnostic.data["call"] == "double(1)"
    assert (finding.diagnostic.severity, finding.diagnostic.line) == (Severity.LOGIC, 1)


def test_crash_in_the_test_call_itself_points_at_the_def_line():
    demo = exercise({"call": "area(3, 4)", "expect": "12"})
    source = "# Areas\n\ndef area(width):\n    return width * width\n"
    [d] = evaluate_tests(demo, source)[1]
    assert (d.code, d.line, d.col, d.end_col) == ("TypeError", 3, 4, 8)
    assert d.data["in_test_call"] is True


def test_runtime_fix_inside_a_function_is_verified_against_the_tests():
    # The typo only crashes when a test calls the function; a plain run of the
    # program would never reach it, so only the tests can verify the fix.
    demo = exercise({"call": "total([1, 2])", "expect": "3"})
    source = "def total(numbers):\n    result = 0\n    for n in numbers:\n        result += n\n    return reslt\n"
    finding = ENGINE.run_exercise(demo, source).blocking
    assert finding.card.id == "name-typo"
    assert ENGINE.run_exercise(demo, finding.fix.source).passed


def test_logic_fix_must_make_its_test_pass():
    demo = exercise({"call": "double(4)", "expect": "8"})
    finding = ENGINE.run_exercise(demo, "def double(n):\n    print(n * 2)\n").findings[0]
    assert finding.card.id == "printed-not-returned"
    assert ENGINE.run_exercise(demo, finding.fix.source).passed


def test_printed_value_that_is_not_the_answer_is_not_called_printed_not_returned():
    demo = exercise({"call": "double(4)", "expect": "8"})
    finding = ENGINE.run_exercise(demo, "def double(n):\n    print('working...')\n").findings[0]
    assert finding.card.id == "missing-return"


def test_report_serialises_for_the_browser():
    demo = exercise({"call": "double(4)", "expect": "8"})
    data = ENGINE.run_exercise(demo, "def double(n):\n    return 8\n").to_dict()
    assert data["passed"] is True
    assert data["results"][0]["test"]["call"] == "double(4)"
