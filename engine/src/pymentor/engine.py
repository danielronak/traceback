"""The public engine API: everything the app, the extension and the data
pipeline need, in two calls.

- ``check(source)``: the live, static check (syntax and style). Fast and
  side-effect free, so it is safe to call whenever typing pauses (D7).
- ``run(source, inputs)``: the static check, then runs the program.

Exercises add ``run_exercise(exercise, source)``, which runs the exercise's
tests and turns failures into logic findings.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import fixes
from .cards import CardLibrary, CardRenderError
from .exercises import Exercise, ExerciseReport, run_exercise
from .facts import Diagnostic, Finding, Fix, Severity
from .features import extract
from .sandbox import DEFAULT_STEP_LIMIT, DEFAULT_TIME_LIMIT, Inputs, RunResult, execute
from .source import changed_region, lines
from .style import check_style
from .syntax import check_syntax

# (source, inputs, step_limit, time_limit) -> RunResult. ``sandbox.execute`` runs
# in-process; ``isolated.run_isolated`` runs in a killable subprocess.
Runner = Callable[..., RunResult]

_SEVERITY_ORDER = {Severity.SYNTAX: 0, Severity.RUNTIME: 1, Severity.LOGIC: 2, Severity.STYLE: 3}


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    ran: bool = False
    stdout: str = ""
    inputs_used: list[str] = field(default_factory=list)

    @property
    def blocking(self) -> Finding | None:
        """The syntax or runtime error the learner should fix first, if any."""
        return next((f for f in self.findings if f.diagnostic.severity.blocking), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "ran": self.ran,
            "stdout": self.stdout,
            "inputs_used": self.inputs_used,
        }


class Engine:
    def __init__(
        self,
        cards: CardLibrary | None = None,
        *,
        runner: Runner = execute,
        step_limit: int = DEFAULT_STEP_LIMIT,
        time_limit: float = DEFAULT_TIME_LIMIT,
    ) -> None:
        self.cards = cards if cards is not None else CardLibrary.load()
        self.runner = runner
        self.step_limit = step_limit
        self.time_limit = time_limit

    # --- the two calls -----------------------------------------------------

    def check(self, source: str) -> Report:
        """Syntax and style only. Never runs the learner's code."""
        return Report(findings=self._static(source))

    def run(self, source: str, inputs: Inputs = None) -> Report:
        """The static check, then a run, if the code compiles."""
        findings = self._static(source)
        if any(f.diagnostic.severity is Severity.SYNTAX for f in findings):
            return Report(findings=findings)
        result = self._execute(source, inputs)
        if result.diagnostic is not None:
            findings.append(self.explain(result.diagnostic, source, result.inputs_used))
        return Report(
            findings=_ordered(findings),
            ran=True,
            stdout=result.stdout,
            inputs_used=result.inputs_used,
        )

    # --- building findings ---------------------------------------------------

    def run_exercise(self, exercise: Exercise, source: str) -> ExerciseReport:
        """Run an exercise's tests against the learner's code (see ``exercises``)."""
        return run_exercise(self, exercise, source)

    def explain(
        self,
        diagnostic: Diagnostic,
        source: str,
        inputs: list[str] = (),
        *,
        with_fix: bool = True,
        recheck: fixes.Recheck | None = None,
    ) -> Finding:
        """Match a diagnostic to its card and find a verified fix.

        ``recheck`` re-derives the facts for a candidate fix when a plain run
        can't (exercise tests); see ``fixes.verify``.
        """
        features = extract(diagnostic, source)
        card = self.cards.match(diagnostic, features)
        rendered = None
        if card is not None:
            try:
                rendered = card.render(features)
            except CardRenderError:
                card = None  # a card that can't be filled in is not shown (tests prevent this)
        fix = None
        if card is not None and with_fix:
            fix = self._fix(card.fix, diagnostic, source, features, list(inputs), recheck)
        return Finding(diagnostic, rendered, fix, features)

    def _fix(
        self,
        spec: str | None,
        diagnostic: Diagnostic,
        source: str,
        features: dict[str, Any],
        inputs: list[str],
        recheck: fixes.Recheck | None = None,
    ) -> Fix | None:
        if spec is None:
            return None
        for candidate in fixes.candidates(spec, source, diagnostic, features):
            if fixes.verify(diagnostic, candidate, self._replay, inputs, recheck):
                line, before, after = changed_region(source, candidate)
                return Fix(source=candidate, before=before, after=after, line=line)
        return None

    def _static(self, source: str) -> list[Finding]:
        syntax_error = check_syntax(source)
        if syntax_error is None:
            return [self.explain(d, source) for d in check_style(ast.parse(source))]
        finding = self.explain(syntax_error, source)
        return [finding, *self._style_behind(finding, source)]

    def _style_behind(self, blocking: Finding, source: str) -> list[Finding]:
        """Style findings for the rest of a file that a syntax error stops compiling.

        Style checks need a syntax tree, so we check the file as it would be
        after the syntax error's verified fix. Only fixes that keep every line
        in place qualify, so positions stay true for the learner's file. Lines
        the fix changes are skipped, and these findings carry no fix of their
        own until the file compiles.
        """
        fix = blocking.fix
        if fix is None or len(lines(fix.source)) != len(lines(source)):
            return []
        if check_syntax(fix.source) is not None:
            return []
        changed = range(fix.line, fix.line + max(1, len(fix.before.splitlines())))
        return [
            self.explain(d, fix.source, with_fix=False)
            for d in check_style(ast.parse(fix.source))
            if d.line not in changed
        ]

    def _execute(self, source: str, inputs: Inputs) -> RunResult:
        return self.runner(source, inputs, step_limit=self.step_limit, time_limit=self.time_limit)

    def _replay(self, source: str, inputs: list[str]) -> RunResult:
        # Fixes are verified with exactly the input the learner typed.
        return self._execute(source, inputs)


def _ordered(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_ORDER[f.diagnostic.severity], f.diagnostic.line, f.diagnostic.col),
    )
