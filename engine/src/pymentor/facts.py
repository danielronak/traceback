"""The facts the engine produces.

Everything in this module is produced by deterministic tooling (Python's own
compiler, the sandbox, the style checks, exercise tests). The tutor model only
ever *reads* these objects; it never creates them.

Conventions: lines are 1-based, columns are 0-based character offsets (the
same as ``ast`` and ``traceback``), and end positions are exclusive.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """The four kinds of mistake, each with its own colour in the editor."""

    SYNTAX = "syntax"  # red: Python can't compile the file, nothing runs
    RUNTIME = "runtime"  # orange: valid syntax that crashes when run
    STYLE = "style"  # blue: works, but doesn't read like Python
    LOGIC = "logic"  # purple: runs fine, wrong answer (exercise tests)

    @property
    def blocking(self) -> bool:
        return self in (Severity.SYNTAX, Severity.RUNTIME)


@dataclass(frozen=True)
class Diagnostic:
    """One verified problem in the learner's code."""

    severity: Severity
    code: str  # exception type ("NameError") or style/logic rule code
    message: str  # Python's own message, unedited
    line: int
    col: int = 0
    end_line: int | None = None
    end_col: int | None = None
    data: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def location(self) -> tuple[int, int]:
        return (self.line, self.col)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Diagnostic:
        return cls(**{**d, "severity": Severity(d["severity"])})


@dataclass(frozen=True)
class Fix:
    """A concrete correction.

    Fix objects only exist once the engine has re-checked the fixed program and
    confirmed this error is gone (see ``fixes.verify``); broken fixes are dropped.
    """

    source: str  # the whole program after the fix
    before: str  # the original text of the changed line(s)
    after: str  # the corrected text of those line(s)
    line: int  # first changed line in the original program


@dataclass(frozen=True)
class RenderedCard:
    """A rule card with its placeholders filled in for one diagnostic."""

    id: str
    title: str
    rule: str
    why: str
    hints: tuple[str, ...]
    exceptions: str = ""
    related: tuple[str, ...] = ()


@dataclass(frozen=True)
class Finding:
    """What the UI shows for one problem: the fact, its card and its fix."""

    diagnostic: Diagnostic
    card: RenderedCard | None
    fix: Fix | None
    features: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def confidence(self) -> str:
        # Without a card the explanation rests on Python's raw message alone,
        # and the UI marks it as lower confidence.
        return "high" if self.card is not None else "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnostic": self.diagnostic.to_dict(),
            "card": asdict(self.card) if self.card else None,
            "fix": asdict(self.fix) if self.fix else None,
            "confidence": self.confidence,
        }
