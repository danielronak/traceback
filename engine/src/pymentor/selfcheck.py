"""Self-checks for the card library and the curriculum.

These run wherever the engine runs: under pytest on CPython, and inside
Pyodide in the app's CI, so the cards are proven on the exact Python the
browser ships (D15). Error messages differ between Python versions, so a card
that passes on one can silently stop matching on another.

Each check returns a list of problems; an empty list means it passed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .exercises import Exercise
from .facts import Finding, Severity

if TYPE_CHECKING:
    from .cards import Card, Example
    from .course import Course
    from .engine import Engine


def label(finding: Finding | None) -> str:
    if finding is None:
        return "<nothing>"
    d = finding.diagnostic
    return finding.card.id if finding.card else f"<no card: {d.code}: {d.message}>"


def check_example(engine: Engine, card: Card, example: Example) -> list[str]:
    """The example triggers this card (first, if it's an error) and its fix verifies."""
    if example.tests:
        report = engine.run_exercise(
            Exercise("example", "Example", "", "", "", example.tests), example.source
        )
    else:
        report = engine.run(example.source, list(example.inputs))
    finding = next((f for f in report.findings if f.card and f.card.id == card.id), None)
    if finding is None:
        return [f"{card.id}: example triggered {[label(f) for f in report.findings]} instead"]
    problems = []
    if finding.diagnostic.severity.blocking and report.blocking is not finding:
        # An error card must explain the error the learner has to fix first.
        problems.append(f"{card.id}: triggered, but {label(report.blocking)} comes first")
    if card.fix is not None:
        if example.no_fix and finding.fix is not None:
            problems.append(f"{card.id}: example is marked no_fix but got a fix")
        elif not example.no_fix and finding.fix is None:
            problems.append(f"{card.id}: {card.fix} produced no verified fix")
        elif example.after is not None and finding.fix.after != example.after:
            problems.append(
                f"{card.id}: fix gives {finding.fix.after!r}, expected {example.after!r}"
            )
    return problems


def check_library(engine: Engine) -> list[str]:
    problems = []
    for card in engine.cards:
        for example in card.examples:
            problems.extend(check_example(engine, card, example))
        if card.fix and not any(e.after for e in card.examples):
            problems.append(f"{card.id}: add an `after` to one example to show the fix's result")
    return problems


def check_exercise(engine: Engine, exercise: Exercise) -> list[str]:
    """The solution passes with no findings at all; the starter compiles, fails and is taught."""
    problems = []
    solved = engine.run_exercise(exercise, exercise.solution)
    if not solved.passed:
        failed = [r.test.to_dict() for r in solved.results if not r.passed]
        problems.append(f"{exercise.id}: the solution fails {failed}")
    if solved.findings:
        # Solutions are what learners compare against, so they must be exemplary.
        problems.append(
            f"{exercise.id}: the solution has findings {[label(f) for f in solved.findings]}"
        )
    started = engine.run_exercise(exercise, exercise.starter)
    if any(f.diagnostic.severity is Severity.SYNTAX for f in started.findings):
        problems.append(f"{exercise.id}: the starter doesn't compile")
    if started.passed:
        problems.append(f"{exercise.id}: the starter already passes every test")
    elif not started.findings or started.findings[0].card is None:
        first = started.findings[0] if started.findings else None
        problems.append(f"{exercise.id}: the starter's first finding has no card: {label(first)}")
    return problems


def check_course(engine: Engine, course: Course) -> list[str]:
    """Lessons name real cards, ordinary snippets run cleanly, and each broken
    snippet is taught by exactly the card it names (which the lesson lists)."""
    problems = []
    for lesson in course.lessons.values():
        for card_id in lesson.teaches:
            if card_id not in engine.cards.by_id:
                problems.append(f"{lesson.id}: teaches unknown card '{card_id}'")
        for number, snippet in enumerate(lesson.snippets, start=1):
            where = f"{lesson.id} snippet {number}"
            report = engine.run(snippet.code, list(snippet.inputs))
            found = [label(f) for f in report.findings]
            if snippet.broken is None:
                if found:
                    problems.append(f"{where}: should run cleanly but has {found}")
            elif not found or found[0] != snippet.broken:
                problems.append(f"{where}: should be taught by '{snippet.broken}' but got {found}")
            elif snippet.broken not in lesson.teaches:
                problems.append(
                    f"{where}: shows '{snippet.broken}', so the lesson should list it in teaches"
                )
    return problems
