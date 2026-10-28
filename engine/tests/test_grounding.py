import pytest

from pymentor import CardLibrary, Engine
from pymentor.exercises import Exercise
from pymentor.grounding import check, compiles, is_grounded

ENGINE = Engine(step_limit=20_000)
SOURCE = "total = 0\nfor n in [1, 2, 3]:\n    total += n\nprint(totl)\n"
FINDING = ENGINE.run(SOURCE).blocking  # name-typo on line 4


def problems(text, task="explain", finding=FINDING, source=SOURCE):
    return [p.check for p in check(text, finding, source, task)]


def test_a_faithful_explanation_passes():
    text = "On line 4 you wrote `totl`, but the variable you built up is `total`. Python sees a new name. Use `print(total)`."
    assert problems(text) == []


def test_line_numbers_must_come_from_the_facts():
    assert problems("The mistake is on line 7.") == ["line"]
    assert problems("Look at lines 4 and 9.") == ["line"]


def test_code_may_only_use_names_that_exist():
    assert problems("Change it to `print(grand_total)`.") == ["name"]
    assert problems("Try `print(total)` or `len(str(total))`.") == []
    assert problems("Text in quotes is fine: `print('anything at all')`.") == []


def test_code_blocks_must_compile():
    assert problems("Write:\n```python\nprint(total\n```") == ["code"]


def test_error_types_must_match():
    assert problems("This is a TypeError.") == ["error-type"]
    assert problems("This NameError means Python can't find the name.") == []


def test_early_hints_must_not_reveal_the_fix():
    assert problems("Try writing print(total) instead.", task="hint_level_1") == ["leak"]
    assert problems("Try writing print(total) instead.", task="hint_level_3") == []


def test_length_and_emptiness():
    assert problems("word " * 200) == ["length"]
    assert problems("   ") == ["empty"]


def test_feature_lines_are_allowed():
    source = "age = input()\nprint(age + 1)\n"
    finding = ENGINE.run(source, ["4"]).blocking
    assert is_grounded(
        "`age` gets its value from `input()` on line 1, so on line 2 it's text.",
        finding,
        source,
        "explain",
    )


# The card text is the no-model baseline (D12) and must itself be grounded,
# rendered for every example the card ships with.
LIBRARY = CardLibrary.load()
CASES = [
    pytest.param(card, example, id=f"{card.id}-{n}")
    for card in LIBRARY
    for n, example in enumerate(card.examples)
]


@pytest.mark.parametrize(("card", "example"), CASES)
def test_every_cards_own_text_is_grounded(card, example):
    if example.tests:
        report = ENGINE.run_exercise(Exercise("x", "X", "", "", "", example.tests), example.source)
    else:
        report = ENGINE.run(example.source, list(example.inputs))
    finding = next(f for f in report.findings if f.card and f.card.id == card.id)
    rendered = finding.card
    texts = {
        "explain": f"{rendered.title}. {rendered.rule}",
        "why_followup": rendered.why,
        **{f"hint_level_{i + 1}": hint for i, hint in enumerate(rendered.hints)},
    }
    for task, text in texts.items():
        assert [str(p) for p in check(text, finding, example.source, task)] == [], task


def test_ranges_with_an_en_dash_are_read():
    assert problems("See lines 4–9.") == ["line"]  # noqa: RUF001 (the en dash is the point)


def test_a_fix_line_lifted_from_a_program_counts_as_code():
    # A corrected block header or indented line is valid on its own terms...
    for block in ("for name in ages:", "    return total", "while x <= 3:\n    x += 1"):
        assert compiles(block), block
    # ...but a line that is itself wrong still isn't.
    for block in ("if x = 5:", "print(score", "for name in ages"):
        assert not compiles(block), block


def _finding(source):
    return Engine().run(source).findings[0]


NAME_TYPO = "year = 2024\nlabel = 'Year'\nprint(label)\nprint(yera)\n"


def test_another_line_is_fine_when_the_sentence_quotes_its_code():
    finding = _finding(NAME_TYPO)
    good = "You probably meant `year`, which you created on line 1."
    assert not [p for p in check(good, finding, NAME_TYPO, "explain") if p.check == "line"]
    wrong = "You created `year` on line 2."  # line 2 holds `label`, not `year`
    assert [p for p in check(wrong, finding, NAME_TYPO, "explain") if p.check == "line"]
    bare = "Look at line 2."
    assert [p for p in check(bare, finding, NAME_TYPO, "explain") if p.check == "line"]


def test_statements_in_backticks_must_come_from_the_code_card_or_fix():
    finding = _finding(NAME_TYPO)
    assert finding.fix is not None and "print(year)" in finding.fix.after
    quoted = "Line 4 says `print(yera)`; you wrote `year = 2024` earlier."
    assert not [p for p in check(quoted, finding, NAME_TYPO, "explain") if p.check == "code"]
    invented = "Write `year = 0` first."
    problems = [p for p in check(invented, finding, NAME_TYPO, "explain") if p.check == "code"]
    assert problems and "year = 0" in problems[0].detail


@pytest.mark.parametrize(
    ("source", "task", "text"),
    [
        ("print(Sam)\n", "hint_level_1", 'Is `Sam` text? Then it needs quote marks: `"Sam"`.'),
        ("items = []\nitems.appned(3)\n", "hint_level_1", "Did you mean `.append` on line 2?"),
        ("nums = [1 2, 3]\n", "hint_level_1", "Look at line 1. Is a comma missing?"),
        ("x = 1\nprnit(x)\n", "hint_level_2", "Line 2 has `prnit` instead of `print`."),
    ],
)
def test_early_hints_must_not_name_what_the_fix_adds(source, task, text):
    assert [p.check for p in check(text, _finding(source), source, task)] == ["leak"]


def test_an_early_hint_may_say_what_the_cards_own_hint_says():
    source = "x = 1\nif x > 0\n    print(x)\n"  # the fix adds a colon
    finding = _finding(source)
    assert finding.fix is not None
    assert (
        check(
            "Look at the very end of line 2. Is something missing?", finding, source, "hint_level_1"
        )
        == []
    )
    assert [p.check for p in check("Line 2 needs a colon.", finding, source, "hint_level_1")] == [
        "leak"
    ]
    # The same words are fine once the near-answer step is reached.
    assert check("Line 2 needs a colon.", finding, source, "hint_level_3") == []
