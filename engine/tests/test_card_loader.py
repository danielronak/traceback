import pytest

from pymentor.cards import CardError, CardLibrary, CardRenderError, parse_cards
from pymentor.facts import Diagnostic, Severity

CARD = """
[[card]]
id = "{id}"
title = "Title {{name}}"
match = {match}
rule = "Rule."
why = "Why."
hints = ["One."]
examples = [{{ source = "x\\n" }}]
{extra}
"""


def card(id="demo", match='{ code = "NameError" }', extra=""):
    return CARD.format(id=id, match=match, extra=extra)


def library(*texts):
    return CardLibrary([c for t in texts for c in parse_cards(t, "test.toml")])


@pytest.mark.parametrize(
    ("text", "complaint"),
    [
        (card(extra='colour = "red"'), "unknown fields"),
        (card(id="Bad_Id"), "lowercase-with-dashes"),
        (card(match='{ code = "NameError", kind = "x" }'), "unknown match fields"),
        (card(match='{ code = "NameError", message = "(" }'), "bad match.message regex"),
        (card(extra='fix = "no_such_fixer"'), "unknown fix generator"),
        (card().replace('hints = ["One."]', "hints = []"), "1 to 3 strings"),
        (
            card().replace('examples = [{ source = "x\\n" }]', "examples = []"),
            "at least one example",
        ),
    ],
)
def test_malformed_cards_are_rejected_at_load_time(text, complaint):
    with pytest.raises(CardError, match=complaint):
        parse_cards(text, "test.toml")


def test_duplicate_ids_and_unknown_related_cards_are_rejected():
    with pytest.raises(CardError, match="duplicate"):
        library(card(), card())
    with pytest.raises(CardError, match="unknown 'nope'"):
        library(card(extra='related = ["nope"]'))


def test_most_specific_card_wins():
    lib = library(
        card("generic"),
        card("specific", match='{ code = "NameError", when = { similar_name = true } }'),
        card(
            "urgent", match='{ code = "NameError", when = { module = true } }', extra="priority = 5"
        ),
    )
    d = Diagnostic(Severity.RUNTIME, "NameError", "m", line=1)
    assert lib.match(d, {}).id == "generic"
    assert lib.match(d, {"similar_name": "total"}).id == "specific"
    assert lib.match(d, {"similar_name": "total", "module": "math"}).id == "urgent"


def test_conditions_true_false_and_equal():
    lib = library(card(match='{ code = "X", when = { a = true, b = false, c = "int" } }'))
    d = Diagnostic(Severity.RUNTIME, "X", "m", line=1)
    assert lib.match(d, {"a": 1, "b": None, "c": "int"}) is not None
    assert lib.match(d, {"a": 1, "b": None, "c": "str"}) is None
    assert lib.match(d, {"a": 0, "c": "int"}) is None


def test_rendering_refuses_missing_or_none_facts():
    demo = library(card()).by_id["demo"]
    assert demo.render({"name": "x"}).title == "Title x"
    with pytest.raises(CardRenderError):
        demo.render({})
    with pytest.raises(CardRenderError):
        demo.render({"name": None})


def test_bundled_library_loads():
    assert len(CardLibrary.load()) > 0


QUIZ = (
    '\n[card.quiz]\nquestion = "Q?"\nchoices = {choices}\nanswer = {answer}\nexplain = "Because."\n'
)


@pytest.mark.parametrize(
    ("choices", "answer", "complaint"),
    [
        ('["only one"]', 0, "2 to 4 choices"),
        ('["a", "a"]', 0, "distinct"),
        ('["a", "b"]', 2, "index of one of the choices"),
    ],
)
def test_malformed_quizzes_are_rejected(choices, answer, complaint):
    with pytest.raises(CardError, match=complaint):
        parse_cards(card() + QUIZ.format(choices=choices, answer=answer), "test.toml")


def test_quizzes_reach_the_rendered_card_untemplated():
    [demo] = parse_cards(card() + QUIZ.format(choices='["{a}", "b"]', answer=1), "test.toml")
    rendered = demo.render({"name": "x"})
    assert rendered.quiz.choices == ("{a}", "b") and rendered.quiz.answer == 1
