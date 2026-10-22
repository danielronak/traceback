from pymentor import fixes
from pymentor.facts import Diagnostic, Severity
from pymentor.sandbox import execute
from pymentor.syntax import check_syntax


def run(source, inputs):
    return execute(source, inputs, step_limit=5_000)


def test_syntax_fix_may_reveal_a_later_error_but_not_one_at_its_line():
    original = check_syntax("if x > 2\n    pass\nprint('a'\n")
    assert fixes.verify(original, "if x > 2:\n    pass\nprint('a'\n", run, [])  # next error: line 3
    assert not fixes.verify(original, "if x > 2::\n    pass\n", run, [])  # still broken at line 1


def test_runtime_fix_is_rerun_with_the_learners_input():
    source = "age = input()\nprint(age + 1)\n"
    original = execute(source, ["4"]).diagnostic
    assert fixes.verify(original, "age = int(input())\nprint(age + 1)\n", run, ["4"])
    # With the input "four", the same fix fails earlier, on line 1, so it's rejected.
    assert not fixes.verify(original, "age = int(input())\nprint(age + 1)\n", run, ["four"])


def test_fix_that_breaks_syntax_is_rejected_for_runtime_errors():
    original = execute("print(1/0)\n").diagnostic
    assert not fixes.verify(original, "print(1/\n", run, [])


def test_rename_skips_attributes_and_refuses_taken_names():
    d = Diagnostic(Severity.STYLE, "naming-variable", "m", line=1)
    source = "Total = 1\nobj.Total = Total\n"
    [renamed] = fixes.candidates("rename:new", source, d, {"name": "Total", "new": "total"})
    assert renamed == "total = 1\nobj.Total = total\n"
    taken = "Total = 1\ntotal = 2\n"
    assert fixes.candidates("rename:new", taken, d, {"name": "Total", "new": "total"}) == []


def test_generator_that_cannot_apply_produces_nothing():
    d = Diagnostic(Severity.RUNTIME, "NameError", "m", line=5, col=0, end_col=3)
    assert fixes.candidates("replace_name:x", "a = 1\n", d, {"name": "foo"}) == []


def test_add_import_goes_after_existing_imports_and_docstrings():
    d = Diagnostic(Severity.RUNTIME, "NameError", "m", line=3)
    source = '"""Doc."""\nimport time\nprint(math.pi)\n'
    [fixed] = fixes.candidates("add_import", source, d, {"module": "math"})
    assert fixed == '"""Doc."""\nimport time\nimport math\nprint(math.pi)\n'
