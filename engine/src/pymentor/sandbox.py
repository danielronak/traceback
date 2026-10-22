"""Runs learner code and turns what happens into facts.

This runs in-process. In the browser it runs inside a Web Worker that the app
can terminate; on CPython, ``isolated.py`` wraps it in a subprocess with a hard
timeout. It is a teaching sandbox, not a security boundary: learners run their
own code on their own device.
"""

from __future__ import annotations

import builtins
import io
import re
import sys
import time
import traceback
from collections import Counter
from collections.abc import Callable, Iterable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Any

from .facts import Diagnostic, Severity
from .source import LEARNER_FILENAME
from .syntax import check_syntax

# Deterministic limits, so the same program always gets the same diagnosis.
# The wall-clock limit is a backstop for slow devices and long builtin calls.
DEFAULT_STEP_LIMIT = 2_000_000
DEFAULT_TIME_LIMIT = 5.0
MAX_OUTPUT_CHARS = 100_000

# How the learner's program receives input(): a list of answers to replay,
# or a callable (the browser's blocking stdin) that takes the prompt.
Inputs = Iterable[str] | Callable[[str], str] | None


class _StopRun(BaseException):
    """Raised inside learner code to stop it. BaseException, so a learner's
    ``except Exception`` can't swallow it."""

    def __init__(self, reason: str, line: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.line = line


class _InputExhausted(EOFError):
    pass


@dataclass
class RunResult:
    stdout: str
    diagnostic: Diagnostic | None
    inputs_used: list[str] = field(default_factory=list)
    steps: int = 0
    # The learner's globals after the run. Exercise tests call functions from
    # here (M2). Never serialised.
    namespace: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stdout": self.stdout,
            "diagnostic": self.diagnostic.to_dict() if self.diagnostic else None,
            "inputs_used": self.inputs_used,
            "steps": self.steps,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunResult:
        diagnostic = Diagnostic.from_dict(d["diagnostic"]) if d["diagnostic"] else None
        return cls(d["stdout"], diagnostic, d["inputs_used"], d["steps"])


class _Output(io.StringIO):
    """Captures output, keeping at most MAX_OUTPUT_CHARS."""

    def write(self, text: str) -> int:
        room = MAX_OUTPUT_CHARS - self.tell()
        if room > 0:
            super().write(text[:room])
        return len(text)


def execute(
    source: str,
    inputs: Inputs = None,
    *,
    step_limit: int = DEFAULT_STEP_LIMIT,
    time_limit: float = DEFAULT_TIME_LIMIT,
) -> RunResult:
    """Run a whole program as ``__main__`` and report the first problem."""
    syntax_error = check_syntax(source)
    if syntax_error is not None:
        return RunResult("", syntax_error)

    code = compile(source, LEARNER_FILENAME, "exec", dont_inherit=True)
    output = _Output()
    used: list[str] = []
    read_input = _make_input(inputs, used, output)
    learner_builtins = dict(vars(builtins))
    learner_builtins["input"] = read_input
    namespace: dict[str, Any] = {"__name__": "__main__", "__builtins__": learner_builtins}

    steps = 0
    deadline = time.monotonic() + time_limit

    def trace_lines(frame, event, arg):
        nonlocal steps
        if event == "line":
            steps += 1
            if steps > step_limit:
                raise _StopRun("steps", frame.f_lineno)
            if steps % 10_000 == 0 and time.monotonic() > deadline:
                raise _StopRun("time", frame.f_lineno)
        return trace_lines

    def trace_calls(frame, event, arg):
        # Only learner frames are traced, which keeps the overhead low.
        return trace_lines if frame.f_code.co_filename == LEARNER_FILENAME else None

    diagnostic = None
    old_trace = sys.gettrace()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            sys.settrace(trace_calls)
            try:
                exec(code, namespace)
            finally:
                sys.settrace(old_trace)
    except _StopRun as stop:
        diagnostic = _stopped(stop, steps, time_limit)
    except SystemExit:
        pass  # exit() and sys.exit() end the program normally
    except BaseException as error:  # learner code can raise anything
        diagnostic = from_exception(error)

    return RunResult(output.getvalue(), diagnostic, used, steps, namespace)


def _make_input(inputs: Inputs, used: list[str], output: io.StringIO) -> Callable[..., str]:
    if callable(inputs):
        provider: Callable[[str], str] = inputs
    else:
        pending = iter(list(inputs or []))

        def provider(prompt: str) -> str:
            try:
                return next(pending)
            except StopIteration:
                raise _InputExhausted("EOF when reading a line") from None

    def read_input(prompt: object = "") -> str:
        prompt_text = str(prompt)
        output.write(prompt_text)
        answer = str(provider(prompt_text))
        output.write(answer + "\n")  # echo, as a terminal would show it
        used.append(answer)
        return answer

    return read_input


def _stopped(stop: _StopRun, steps: int, time_limit: float) -> Diagnostic:
    if stop.reason == "steps":
        message = f"The program was stopped after {steps - 1:,} steps without finishing."
    else:
        message = f"The program was stopped after running for {time_limit:g} seconds."
    return Diagnostic(
        Severity.RUNTIME, "Timeout", message, line=stop.line, data={"reason": stop.reason}
    )


_TYPE_PREFIX = re.compile(r"^[\w.]+(?=: |$)(: )?")


def from_exception(error: BaseException) -> Diagnostic:
    """Facts about an exception, located at the deepest frame in learner code."""
    frames = [
        f for f in traceback.extract_tb(error.__traceback__) if f.filename == LEARNER_FILENAME
    ]
    chunks = list(traceback.TracebackException.from_exception(error).format_exception_only())
    # Python's own message, including suggestions such as "Did you mean: 'total'?".
    # Indented chunks are source excerpts (for SyntaxError); notes come after.
    headline = next((c for c in chunks if not c.startswith(" ")), chunks[-1]).strip()
    message = _TYPE_PREFIX.sub("", headline.splitlines()[0], count=1)
    if isinstance(error, _InputExhausted):
        message = str(error)

    data: dict[str, Any] = {"frames": _collapse([(f.lineno, f.name) for f in frames])}
    if isinstance(error, _InputExhausted):
        data["input_exhausted"] = True
    if isinstance(getattr(error, "name", None), str):  # NameError, AttributeError, ImportError
        data["name"] = error.name
    if isinstance(error, KeyError) and error.args:
        data["key"] = repr(error.args[0])

    code = "EOFError" if isinstance(error, _InputExhausted) else type(error).__name__
    if not frames:  # raised before any learner line ran
        return Diagnostic(Severity.RUNTIME, code, message, line=1, data=data)
    last = frames[-1]
    if isinstance(error, RecursionError):
        # The deepest frame is wherever Python gave up; the lesson is the call
        # that keeps repeating.
        line, name = max(Counter((f.lineno, f.name) for f in frames).items(), key=lambda kv: kv[1])[
            0
        ]
        last = next(f for f in reversed(frames) if (f.lineno, f.name) == (line, name))
    return Diagnostic(
        Severity.RUNTIME,
        code,
        message,
        line=last.lineno or 1,
        col=last.colno or 0,
        end_line=last.end_lineno,
        end_col=last.end_colno,
        data=data,
    )


def _collapse(frames: list[tuple[int | None, str]]) -> list[dict[str, Any]]:
    """Collapse runs of identical frames (deep recursion) into one with a count."""
    collapsed: list[dict[str, Any]] = []
    for line, name in frames:
        if collapsed and collapsed[-1]["line"] == line and collapsed[-1]["function"] == name:
            collapsed[-1]["repeats"] += 1
        else:
            collapsed.append({"line": line, "function": name, "repeats": 1})
    return collapsed
