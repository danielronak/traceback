from pymentor.facts import Severity
from pymentor.syntax import check_syntax


def test_valid_code_has_no_syntax_error():
    assert check_syntax("x = 1\nprint(x)\n") is None


def test_positions_are_normalised_to_zero_based_columns():
    d = check_syntax("scores = [1]\nif len(scores) > 2\n    print('x')\n")
    assert (d.severity, d.code, d.message) == (Severity.SYNTAX, "SyntaxError", "expected ':'")
    assert (d.line, d.col) == (2, 18)  # Python's offset is 19, 1-based


def test_indentation_errors_keep_their_own_code():
    assert check_syntax("if True:\nprint('x')\n").code == "IndentationError"
    assert check_syntax("if True:\n\tx = 1\n        y = 2\n").code == "TabError"


def test_missing_end_positions_become_none():
    d = check_syntax("x = 1\n    y = 2\n")  # Python reports end_offset -1
    assert d.end_col is None


def test_null_bytes_are_reported_not_raised():
    assert check_syntax("x = 1\x00\n").code == "SyntaxError"
