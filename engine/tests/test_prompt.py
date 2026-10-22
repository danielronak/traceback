import pytest

from pymentor import Engine
from pymentor.prompt import SPECIAL_TOKENS, TASKS, build, code_window, target, tasks_for

ENGINE = Engine(step_limit=20_000)
MOCKUP = (
    'scores = [72, 85, 90]\nif len(scores) > 2\n    print("Enough scores")\nTotal = sum(scores)\n'
)


def test_the_documented_example():
    finding = ENGINE.check(MOCKUP).findings[0]
    prompt = build(finding, MOCKUP, "hint_level_1")
    assert prompt.splitlines()[:4] == [
        "<|task|>hint_level_1",
        "<|level|>beginner",
        "<|error|>SyntaxError line 2: expected ':'",
        "<|card|>Missing colon on line 2",
    ]
    assert "<|hint|>Look at the very end of line 2." in prompt
    assert prompt.endswith(
        '<|code|>\n1 scores = [72, 85, 90]\n2 if len(scores) > 2\n3     print("Enough scores")\n4 Total = sum(scores)\n<|response|>'
    )
    assert "<|fix|>" not in prompt  # an early hint never sees the fix


def test_explain_sees_the_fix_and_why_followup_sees_the_question():
    finding = ENGINE.check(MOCKUP).findings[0]
    assert "<|fix|>before:\nif len(scores) > 2\nafter:\nif len(scores) > 2:" in build(
        finding, MOCKUP, "explain"
    )
    why = build(finding, MOCKUP, "why_followup", question="Why not curly braces?")
    assert "<|question|>Why not curly braces?" in why


def test_window_widens_to_a_short_enclosing_function():
    source = (
        "def total(items):\n"
        + "".join(f"    x{i} = {i}\n" for i in range(8))
        + "    return reslt\n\nprint(total([1]))\n"
    )
    finding = ENGINE.run(source).blocking
    window = code_window(source, finding.diagnostic.line)
    assert window[0] == (1, "def total(items):")
    assert window[-1][0] >= finding.diagnostic.line


def test_window_for_long_programs_is_the_error_line_plus_three():
    source = (
        "".join(f"a{i} = {i}\n" for i in range(20))
        + "print(missing)\n"
        + "".join(f"b{i} = {i}\n" for i in range(20))
    )
    finding = ENGINE.run(source).blocking
    assert [n for n, _ in code_window(source, finding.diagnostic.line)] == list(range(18, 25))


def test_cardless_findings_say_so_and_get_one_task():
    source = "raise RuntimeError('boom')\n"
    finding = ENGINE.run(source).blocking
    assert "<|card|>none" in build(finding, source, "explain")
    assert tasks_for(finding) == ["explain"]


def test_unknown_tasks_and_levels_are_refused():
    finding = ENGINE.check(MOCKUP).findings[0]
    with pytest.raises(ValueError):
        build(finding, MOCKUP, "poem")
    with pytest.raises(ValueError):
        build(finding, MOCKUP, "explain", level="expert")


def test_targets_end_with_the_end_token():
    assert target("  Add a colon.\n") == "Add a colon.<|end|>"
    assert "<|end|>" in SPECIAL_TOKENS and len(TASKS) == 7
