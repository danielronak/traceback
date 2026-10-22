"""PyMentor's deterministic correction engine.

The engine owns the truth: every fact a learner sees (whether there is a
mistake, where, how serious, the rule, and whether a fix works) comes from
here. See docs/architecture.md.
"""

from .cards import Card, CardError, CardLibrary
from .engine import Engine, Report
from .facts import Diagnostic, Finding, Fix, RenderedCard, Severity

__version__ = "0.1.0.dev0"

__all__ = [
    "Card",
    "CardError",
    "CardLibrary",
    "Diagnostic",
    "Engine",
    "Finding",
    "Fix",
    "RenderedCard",
    "Report",
    "Severity",
]
