"""Findings as JSON, and back again.

``Finding.to_dict`` is the app's contract and leaves out the features, which
the grounding checker needs (an `if` header's line, the `input()` line). The
pipeline's files store both, so any later step can rebuild the exact finding
the prompt was made from.
"""

from __future__ import annotations

from typing import Any

from pymentor.facts import Diagnostic, Finding, Fix, Quiz, RenderedCard

JSON_SCALARS = (str, int, float, bool, type(None))


def finding_to_record(finding: Finding) -> dict[str, Any]:
    record = finding.to_dict()
    del record["confidence"]  # derived from the card
    record["features"] = {key: value for key, value in finding.features.items() if _is_json(value)}
    return record


def finding_from_record(record: dict[str, Any]) -> Finding:
    card = record.get("card")
    if card is not None:
        quiz = card.get("quiz")
        card = RenderedCard(
            **{
                **card,
                "hints": tuple(card["hints"]),
                "related": tuple(card["related"]),
                "quiz": Quiz(**{**quiz, "choices": tuple(quiz["choices"])}) if quiz else None,
            }
        )
    fix = Fix(**record["fix"]) if record.get("fix") else None
    return Finding(
        Diagnostic.from_dict(record["diagnostic"]), card, fix, dict(record.get("features", {}))
    )


def _is_json(value: object) -> bool:
    if isinstance(value, list | tuple):
        return all(isinstance(item, JSON_SCALARS) for item in value)
    return isinstance(value, JSON_SCALARS)
