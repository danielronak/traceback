"""Rule cards: the verified teaching knowledge, stored as data.

A card applies to a diagnostic when its ``code`` matches, its optional
``message`` regex matches Python's message, and every ``when`` condition holds
against the extracted features. Among applicable cards the most specific
wins: highest ``priority`` first, then the most conditions (the message
pattern counts as one), then file order.

Conditions compare a feature to a value: ``true`` means the feature is
truthy, ``false`` means falsy (or missing), and anything else must be equal.
"""

from __future__ import annotations

import re
import string
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from .exercises import ExerciseTest, parse_tests
from .facts import Diagnostic, RenderedCard
from .fixes import has_generator

CARD_FIELDS = {
    "id", "title", "match", "priority", "rule", "why", "hints", "fix",
    "exceptions", "related", "examples",
}  # fmt: skip
MATCH_FIELDS = {"code", "message", "when"}
EXAMPLE_FIELDS = {"source", "inputs", "after", "no_fix", "tests"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class CardError(ValueError):
    """A card is malformed. Raised at load time, so broken cards never ship."""


@dataclass(frozen=True)
class Example:
    """A minimal program that must trigger its card (checked by the test suite)."""

    source: str
    inputs: tuple[str, ...] = ()
    after: str | None = None  # the expected fixed line(s), if the card has a fix
    no_fix: bool = False  # the card's fix doesn't apply to this example
    # Exercise tests to run the example against, for cards about test failures.
    tests: tuple[ExerciseTest, ...] = ()


@dataclass(frozen=True)
class Card:
    id: str
    title: str
    codes: tuple[str, ...]
    message: re.Pattern[str] | None
    when: tuple[tuple[str, Any], ...]
    priority: int
    rule: str
    why: str
    hints: tuple[str, ...]
    fix: str | None
    exceptions: str
    related: tuple[str, ...]
    examples: tuple[Example, ...]
    origin: str  # file the card came from, for error messages

    @property
    def specificity(self) -> tuple[int, int]:
        return (self.priority, len(self.when) + (self.message is not None))

    def matches(self, diagnostic: Diagnostic, features: dict[str, Any]) -> bool:
        if diagnostic.code not in self.codes:
            return False
        if self.message is not None and not self.message.search(diagnostic.message):
            return False
        return all(_holds(features.get(key), expected) for key, expected in self.when)

    def render(self, facts: dict[str, Any]) -> RenderedCard:
        """Fill the card's placeholders from diagnostic facts and features."""
        return RenderedCard(
            id=self.id,
            title=_fill(self.title, facts, self.id),
            rule=_fill(self.rule, facts, self.id),
            why=_fill(self.why, facts, self.id),
            hints=tuple(_fill(h, facts, self.id) for h in self.hints),
            exceptions=_fill(self.exceptions, facts, self.id),
            related=self.related,
        )

    def placeholders(self) -> set[str]:
        texts = [self.title, self.rule, self.why, self.exceptions, *self.hints]
        return {
            field
            for text in texts
            for _, field, _, _ in string.Formatter().parse(text)
            if field is not None
        }


def _holds(actual: Any, expected: Any) -> bool:
    if expected is True:
        return bool(actual)
    if expected is False:
        return not actual
    return actual == expected


class CardRenderError(KeyError):
    pass


class _Facts(dict):
    def __init__(self, facts: dict[str, Any], card_id: str) -> None:
        super().__init__(facts)
        self.card_id = card_id

    def __missing__(self, key: str) -> Any:
        raise CardRenderError(f"card '{self.card_id}' needs '{key}', which isn't available")

    def __getitem__(self, key: str) -> Any:
        value = super().__getitem__(key)
        if value is None:
            raise CardRenderError(f"card '{self.card_id}' needs '{key}', which is None here")
        return value


def _fill(text: str, facts: dict[str, Any], card_id: str) -> str:
    return string.Formatter().vformat(text, (), _Facts(facts, card_id))


class CardLibrary:
    """All rule cards, loaded and validated."""

    def __init__(self, cards: Iterable[Card]) -> None:
        self.cards = list(cards)
        self.by_id: dict[str, Card] = {}
        for card in self.cards:
            if card.id in self.by_id:
                raise CardError(f"{card.origin}: duplicate card id '{card.id}'")
            self.by_id[card.id] = card
        for card in self.cards:
            for related in card.related:
                if related not in self.by_id:
                    raise CardError(f"{card.origin}: '{card.id}' relates to unknown '{related}'")

    @classmethod
    def load(cls, paths: Iterable[Path] | None = None) -> CardLibrary:
        """Load the given TOML files, or the library bundled with the package."""
        if paths is None:
            folder = resources.files("pymentor") / "cards"
            files = sorted(
                (f for f in folder.iterdir() if f.name.endswith(".toml")), key=lambda f: f.name
            )
            texts = [(f.name, f.read_text(encoding="utf-8")) for f in files]
        else:
            texts = [(str(p), Path(p).read_text(encoding="utf-8")) for p in paths]
        cards: list[Card] = []
        for origin, text in texts:
            cards.extend(parse_cards(text, origin))
        return cls(cards)

    def match(self, diagnostic: Diagnostic, features: dict[str, Any]) -> Card | None:
        candidates = [c for c in self.cards if c.matches(diagnostic, features)]
        if not candidates:
            return None
        # max() keeps the first of equals, so file order breaks the final tie.
        return max(candidates, key=lambda c: c.specificity)

    def __iter__(self):
        return iter(self.cards)

    def __len__(self) -> int:
        return len(self.cards)


def parse_cards(text: str, origin: str) -> list[Card]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise CardError(f"{origin}: invalid TOML: {error}") from error
    if set(data) - {"card"}:
        raise CardError(f"{origin}: unexpected top-level keys {sorted(set(data) - {'card'})}")
    return [_parse_card(entry, origin) for entry in data.get("card", [])]


def _parse_card(entry: dict[str, Any], origin: str) -> Card:
    card_id = entry.get("id", "<missing id>")
    where = f"{origin}: card '{card_id}'"

    def need(key: str, kind: type) -> Any:
        if key not in entry:
            raise CardError(f"{where}: missing '{key}'")
        if not isinstance(entry[key], kind):
            raise CardError(f"{where}: '{key}' must be {kind.__name__}")
        return entry[key]

    if unknown := set(entry) - CARD_FIELDS:
        raise CardError(f"{where}: unknown fields {sorted(unknown)}")
    if not ID_PATTERN.match(need("id", str)):
        raise CardError(f"{where}: ids are lowercase-with-dashes")

    match = need("match", dict)
    if unknown := set(match) - MATCH_FIELDS:
        raise CardError(f"{where}: unknown match fields {sorted(unknown)}")
    codes = match.get("code")
    codes = (codes,) if isinstance(codes, str) else tuple(codes or ())
    if not codes or not all(isinstance(c, str) for c in codes):
        raise CardError(f"{where}: match.code must be a string or a list of strings")
    try:
        message = re.compile(match["message"]) if "message" in match else None
    except re.error as error:
        raise CardError(f"{where}: bad match.message regex: {error}") from error
    when = match.get("when", {})
    if not isinstance(when, dict):
        raise CardError(f"{where}: match.when must be a table")

    hints = need("hints", list)
    if not 1 <= len(hints) <= 3 or not all(isinstance(h, str) for h in hints):
        raise CardError(f"{where}: 'hints' must be 1 to 3 strings, gentlest first")

    examples = []
    for example in need("examples", list):
        if not isinstance(example, dict) or "source" not in example:
            raise CardError(f"{where}: each example needs a 'source'")
        if unknown := set(example) - EXAMPLE_FIELDS:
            raise CardError(f"{where}: unknown example fields {sorted(unknown)}")
        examples.append(
            Example(
                source=example["source"],
                inputs=tuple(example.get("inputs", ())),
                after=example.get("after"),
                no_fix=bool(example.get("no_fix", False)),
                tests=parse_tests(example["tests"], where) if "tests" in example else (),
            )
        )
    if not examples:
        raise CardError(f"{where}: needs at least one example")

    fix = entry.get("fix")
    if fix is not None and not has_generator(fix):
        raise CardError(f"{where}: unknown fix generator '{fix}'")

    return Card(
        id=card_id,
        title=need("title", str),
        codes=codes,
        message=message,
        when=tuple(sorted(when.items())),
        priority=int(entry.get("priority", 0)),
        rule=need("rule", str),
        why=need("why", str),
        hints=tuple(hints),
        fix=fix,
        exceptions=entry.get("exceptions", ""),
        related=tuple(entry.get("related", ())),
        examples=tuple(examples),
        origin=origin,
    )
