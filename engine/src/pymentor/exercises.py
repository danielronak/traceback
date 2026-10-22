"""Exercises: a task, starter code, a reference solution, and tests.

Two kinds of test:

- **call** tests run an expression in the learner's namespace and compare
  what it returns: ``call = "double(4)"``, ``expect = "8"``.
- **output** tests run the whole program with the given input and compare
  what it printed (prompts and echoed answers don't count):
  ``inputs = ["3"]``, ``output = "9"``.

A failing test becomes a LOGIC diagnostic (purple), located at the tested
function's ``def`` line. Only the first failure becomes a finding, so the
learner fixes one thing at a time; every test result is still reported.
"""

from __future__ import annotations

import ast
import math
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .facts import Diagnostic, Finding, Severity
from .sandbox import DEFAULT_STEP_LIMIT, DEFAULT_TIME_LIMIT, evaluate, execute
from .syntax import check_syntax

if TYPE_CHECKING:
    from .engine import Engine

EXERCISE_FIELDS = {"id", "title", "prompt", "starter", "solution", "tests", "hints"}
TEST_FIELDS = {"name", "call", "expect", "inputs", "output"}
MAX_REPR = 200


class ExerciseError(ValueError):
    """An exercise or test is malformed. Raised at load time."""


@dataclass(frozen=True)
class ExerciseTest:
    __test__ = False  # not a pytest test class
    call: str | None = None
    expect: Any = None  # the expected value, parsed from a Python literal
    expect_text: str = ""  # that literal as written, for messages
    inputs: tuple[str, ...] = ()
    output: str | None = None
    name: str = ""

    @property
    def kind(self) -> str:
        return "call" if self.call is not None else "output"

    @property
    def function(self) -> str | None:
        """The name of the function a call test calls, if it is a plain call."""
        if self.call is None:
            return None
        node = ast.parse(self.call, mode="eval").body
        return (
            node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "call": self.call,
            "expect": self.expect_text if self.call is not None else None,
            "inputs": list(self.inputs),
            "output": self.output,
        }


@dataclass(frozen=True)
class Exercise:
    id: str
    title: str
    prompt: str
    starter: str
    solution: str
    tests: tuple[ExerciseTest, ...]
    hints: tuple[str, ...] = ()
    origin: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "prompt": self.prompt,
            "starter": self.starter,
            "hints": list(self.hints),
            "tests": [t.to_dict() for t in self.tests],
        }


# --- loading -------------------------------------------------------------------


def parse_tests(raw: Any, where: str) -> tuple[ExerciseTest, ...]:
    if not isinstance(raw, list) or not raw:
        raise ExerciseError(f"{where}: needs at least one test")
    tests = []
    for number, entry in enumerate(raw, start=1):
        here = f"{where}: test {number}"
        if not isinstance(entry, dict):
            raise ExerciseError(f"{here}: must be a table")
        if unknown := set(entry) - TEST_FIELDS:
            raise ExerciseError(f"{here}: unknown fields {sorted(unknown)}")
        if ("call" in entry) == ("output" in entry):
            raise ExerciseError(f"{here}: needs either 'call' (with 'expect') or 'output'")
        inputs = entry.get("inputs", [])
        if not isinstance(inputs, list) or not all(isinstance(i, str) for i in inputs):
            raise ExerciseError(f"{here}: 'inputs' must be a list of strings")
        if "call" in entry:
            if "expect" not in entry:
                raise ExerciseError(f"{here}: a 'call' test needs 'expect'")
            try:
                ast.parse(entry["call"], mode="eval")
                expect = ast.literal_eval(entry["expect"])
            except (SyntaxError, ValueError) as error:
                raise ExerciseError(
                    f"{here}: 'call' and 'expect' must be Python: {error}"
                ) from error
            tests.append(
                ExerciseTest(
                    call=entry["call"],
                    expect=expect,
                    expect_text=entry["expect"],
                    inputs=tuple(inputs),
                    name=entry.get("name", ""),
                )
            )
        else:
            tests.append(
                ExerciseTest(
                    inputs=tuple(inputs), output=entry["output"], name=entry.get("name", "")
                )
            )
    return tuple(tests)


def parse_exercise(text: str, origin: str) -> Exercise:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ExerciseError(f"{origin}: invalid TOML: {error}") from error
    if unknown := set(data) - EXERCISE_FIELDS:
        raise ExerciseError(f"{origin}: unknown fields {sorted(unknown)}")
    for key in ("id", "title", "prompt", "starter", "solution"):
        if not isinstance(data.get(key), str):
            raise ExerciseError(f"{origin}: '{key}' must be a string")
    hints = data.get("hints", [])
    if not isinstance(hints, list) or len(hints) > 3:
        raise ExerciseError(f"{origin}: 'hints' must be a list of at most 3 strings")
    return Exercise(
        id=data["id"],
        title=data["title"],
        prompt=data["prompt"],
        starter=data["starter"],
        solution=data["solution"],
        tests=parse_tests(data.get("tests"), origin),
        hints=tuple(hints),
        origin=origin,
    )


def load_exercises(folder: Path) -> list[Exercise]:
    """Every ``*.toml`` exercise under a folder, in path order."""
    exercises = [
        parse_exercise(path.read_text(encoding="utf-8"), str(path))
        for path in sorted(Path(folder).rglob("*.toml"))
    ]
    seen: set[str] = set()
    for exercise in exercises:
        if exercise.id in seen:
            raise ExerciseError(f"{exercise.origin}: duplicate exercise id '{exercise.id}'")
        seen.add(exercise.id)
    return exercises


# --- running ---------------------------------------------------------------------


@dataclass
class TestResult:
    __test__ = False  # not a pytest test class
    test: ExerciseTest
    passed: bool
    actual: str | None = None  # repr of the returned value, or the printed output
    error: Diagnostic | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "test": self.test.to_dict(),
            "passed": self.passed,
            "actual": self.actual,
            "error": self.error.to_dict() if self.error else None,
        }


@dataclass
class ExerciseReport:
    findings: list[Finding] = field(default_factory=list)
    results: list[TestResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(r.passed for r in self.results)

    @property
    def blocking(self) -> Finding | None:
        return next((f for f in self.findings if f.diagnostic.severity.blocking), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
            "results": [r.to_dict() for r in self.results],
        }


def evaluate_tests(
    exercise: Exercise,
    source: str,
    *,
    step_limit: int = DEFAULT_STEP_LIMIT,
    time_limit: float = DEFAULT_TIME_LIMIT,
) -> tuple[list[TestResult], list[Diagnostic]]:
    """Run every test. Returns the results, and the facts to teach from: each
    distinct crash, then the first failing test."""
    syntax_error = check_syntax(source)
    if syntax_error is not None:
        return [], [syntax_error]
    tree = ast.parse(source)
    limits = {"step_limit": step_limit, "time_limit": time_limit}
    results: list[TestResult] = []
    crashes: list[Diagnostic] = []
    failures: list[Diagnostic] = []
    module_run = None  # call tests share one run of the program's top level

    def crashed(test: ExerciseTest, diagnostic: Diagnostic) -> None:
        results.append(TestResult(test, False, error=diagnostic))
        if not any(_same_place(diagnostic, c) for c in crashes):
            crashes.append(diagnostic)

    for index, test in enumerate(exercise.tests):
        if test.kind == "output":
            run = execute(source, test.inputs, **limits)
            if run.diagnostic is not None:
                crashed(test, run.diagnostic)
                continue
            passed = _same_output(run.printed, test.output)
            results.append(TestResult(test, passed, actual=run.printed))
            if not passed:
                failures.append(_wrong_output(index, test, run.printed, tree))
            continue

        if module_run is None:
            module_run = execute(source, (), **limits)
        if module_run.diagnostic is not None:
            crashed(test, module_run.diagnostic)
            continue
        evaluation = evaluate(module_run.namespace, test.call, test.inputs, **limits)
        if evaluation.diagnostic is not None:
            crashed(test, _in_test(evaluation.diagnostic, test, tree))
            continue
        passed = _same_value(evaluation.value, test.expect)
        actual = _short_repr(evaluation.value)
        results.append(TestResult(test, passed, actual=actual))
        if not passed:
            failures.append(_test_failed(index, test, evaluation.value, evaluation.printed, tree))

    return results, crashes + failures[:1]


def run_exercise(engine: Engine, exercise: Exercise, source: str) -> ExerciseReport:
    """Run an exercise's tests and explain what went wrong, with verified fixes."""
    limits = {"step_limit": engine.step_limit, "time_limit": engine.time_limit}
    results, diagnostics = evaluate_tests(exercise, source, **limits)
    static = engine.check(source).findings
    if diagnostics and diagnostics[0].severity is Severity.SYNTAX:
        return ExerciseReport(findings=static, results=results)

    def recheck(fixed: str) -> list[Diagnostic]:
        # A fix is verified against the exercise's own tests, since an error
        # that only a test call triggers wouldn't show up in a plain run.
        return evaluate_tests(exercise, fixed, **limits)[1]

    findings = [engine.explain(d, source, recheck=recheck) for d in diagnostics]
    return ExerciseReport(findings=findings + static, results=results)


# --- facts for failures ------------------------------------------------------------


def _same_value(actual: Any, expected: Any) -> bool:
    try:
        if isinstance(actual, bool) or isinstance(expected, bool):
            return type(actual) is type(expected) and actual == expected
        if isinstance(actual, float) or isinstance(expected, float):
            return isinstance(actual, int | float) and math.isclose(
                actual, expected, rel_tol=1e-9, abs_tol=1e-9
            )
        return bool(actual == expected)
    except Exception:  # a learner's object with a broken __eq__
        return False


def _same_output(printed: str, expected: str) -> bool:
    def normalised(text: str) -> list[str]:
        return [line.rstrip() for line in text.rstrip().splitlines()]

    return normalised(printed) == normalised(expected)


def _short_repr(value: Any) -> str:
    try:
        text = repr(value)
    except Exception:
        text = f"<{type(value).__name__}>"
    return text if len(text) <= MAX_REPR else text[: MAX_REPR - 3] + "..."


def _short_str(value: Any) -> str:
    try:
        text = str(value)
    except Exception:
        return _short_repr(value)
    return text if len(text) <= MAX_REPR else text[: MAX_REPR - 3] + "..."


def _def_position(tree: ast.Module, name: str | None) -> dict[str, int]:
    """Where a function's name is in its ``def`` line (or line 1 if it has none)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            col = node.col_offset + (
                len("async def ") if isinstance(node, ast.AsyncFunctionDef) else 4
            )
            return {
                "line": node.lineno,
                "col": col,
                "end_line": node.lineno,
                "end_col": col + len(name),
            }
    return {"line": 1, "col": 0}


def _in_test(diagnostic: Diagnostic, test: ExerciseTest, tree: ast.Module) -> Diagnostic:
    """A crash during a test call. If it happened in the call itself (no learner
    frame, e.g. the function is missing or takes different arguments), point at
    the function's ``def`` line instead of line 1."""
    data = {**diagnostic.data, "test_call": test.call, "test_function": test.function}
    if diagnostic.data.get("frames"):
        return replace(diagnostic, data=data)
    data["in_test_call"] = True
    return replace(diagnostic, data=data, **_def_position(tree, test.function))


def _test_failed(
    index: int, test: ExerciseTest, value: Any, printed: str, tree: ast.Module
) -> Diagnostic:
    expected, actual = test.expect_text, _short_repr(value)
    return Diagnostic(
        Severity.LOGIC,
        "test-failed",
        f"{test.call} should return {expected}, but it returned {actual}",
        **_def_position(tree, test.function),
        data={
            "test": index,
            "call": test.call,
            "function": test.function,
            "expected": expected,
            "actual": actual,
            "expected_str": str(test.expect),
            "actual_str": _short_str(value),
            "expected_type": type(test.expect).__name__,
            "actual_type": type(value).__name__,
            "printed": printed,
        },
    )


def _wrong_output(index: int, test: ExerciseTest, printed: str, tree: ast.Module) -> Diagnostic:
    first_print = min(
        (
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ),
        default=1,
    )
    return Diagnostic(
        Severity.LOGIC,
        "wrong-output",
        f"The program printed {printed!r}, but {test.output!r} was expected",
        line=first_print,
        data={
            "test": index,
            "expected": repr(test.output),
            "actual": repr(printed),
            "inputs": list(test.inputs),
        },
    )


def _same_place(a: Diagnostic, b: Diagnostic) -> bool:
    return (a.code, a.line, a.message) == (b.code, b.line, b.message)
