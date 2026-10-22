"""The template baseline (D12): what the app says with no model at all.

It fills each task from the card, the way the app shows a card: the title and
rule to explain, the hint for each rung, and the reason for "why?". A model is
only worth its download if it beats this on the benchmark.
"""

from __future__ import annotations

from .evaluate import Item


def template(item: Item) -> str:
    card = item.finding.card
    if card is None:
        return item.finding.diagnostic.message
    if item.task.startswith("hint_level_"):
        rung = int(item.task.rsplit("_", 1)[1])
        return card.hints[min(rung, len(card.hints)) - 1]
    if item.task == "why_followup":
        return card.why
    return f"{card.title}\n\n{card.rule}"
