"""The card library tests itself: every example must trigger its own card,
every template must render, and every fix must verify (see CLAUDE.md)."""

import pytest

from pymentor.cards import CardLibrary
from pymentor.engine import Engine
from pymentor.exercises import Exercise

LIBRARY = CardLibrary.load()
NON_BLOCKING_CODES = {"test-failed", "wrong-output"}
STYLE_CODES = {
    "naming-variable",
    "naming-function",
    "naming-class",
    "builtin-shadowed",
    "compare-none",
    "compare-bool",
}
BLOCKING_CODES = {c for card in LIBRARY for c in card.codes} - STYLE_CODES - NON_BLOCKING_CODES
ENGINE = Engine(LIBRARY, step_limit=20_000)
EXAMPLES = [
    pytest.param(card, example, id=f"{card.id}-{n}")
    for card in LIBRARY
    for n, example in enumerate(card.examples)
]


def _report(example):
    if example.tests:
        exercise = Exercise("example", "Example", "", "", "", example.tests)
        return ENGINE.run_exercise(exercise, example.source)
    return ENGINE.run(example.source, list(example.inputs))


def _finding_for(example):
    report = _report(example)
    assert report.findings, f"no finding at all for:\n{example.source}"
    # Blocking errors come first; for style cards, look at the style findings.
    return report.findings


def _label(finding):
    if finding is None:
        return "<nothing blocking>"
    d = finding.diagnostic
    return finding.card.id if finding.card else f"<no card: {d.code}: {d.message}>"


@pytest.mark.parametrize(("card", "example"), EXAMPLES)
def test_example_triggers_its_card(card, example):
    findings = _finding_for(example)
    if findings[0].diagnostic.severity.blocking or card.codes[0] in BLOCKING_CODES:
        # An error card must explain the error the learner has to fix first.
        assert _label(_report(example).blocking) == card.id
    else:
        ids = [_label(f) for f in findings]
        assert card.id in ids, f"expected {card.id}, got {ids}"


@pytest.mark.parametrize(("card", "example"), EXAMPLES)
def test_example_fix_verifies(card, example):
    if card.fix is None:
        pytest.skip("card has no fix")
    finding = next(f for f in _finding_for(example) if f.card and f.card.id == card.id)
    if example.no_fix:
        assert finding.fix is None
        return
    assert finding.fix is not None, f"{card.fix} produced no verified fix"
    if example.after is not None:
        assert finding.fix.after == example.after


def test_library_has_the_planned_starter_cards():
    assert len(LIBRARY) >= 40


def test_every_card_with_a_fix_has_an_example_showing_the_result():
    missing = [c.id for c in LIBRARY if c.fix and not any(e.after for e in c.examples)]
    assert not missing, f"add an `after` to one example of: {missing}"
