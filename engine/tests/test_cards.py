"""The card library tests itself: every example must trigger its own card,
every template must render, and every fix must verify (see CLAUDE.md).
The checks live in pymentor.selfcheck so they also run inside Pyodide."""

import pytest

from pymentor.cards import CardLibrary
from pymentor.engine import Engine
from pymentor.selfcheck import check_example

LIBRARY = CardLibrary.load()
ENGINE = Engine(LIBRARY, step_limit=20_000)
EXAMPLES = [
    pytest.param(card, example, id=f"{card.id}-{n}")
    for card in LIBRARY
    for n, example in enumerate(card.examples)
]


@pytest.mark.parametrize(("card", "example"), EXAMPLES)
def test_example_triggers_its_card_and_its_fix_verifies(card, example):
    assert check_example(ENGINE, card, example) == []


def test_library_has_the_planned_starter_cards():
    assert len(LIBRARY) >= 40


def test_every_card_with_a_fix_has_an_example_showing_the_result():
    missing = [c.id for c in LIBRARY if c.fix and not any(e.after for e in c.examples)]
    assert not missing, f"add an `after` to one example of: {missing}"
