"""The sandbox in a separate process, with a hard timeout.

Used on CPython by the CLI and the data pipeline, where programs are run in
bulk and one must never hang the whole job. Not available in Pyodide, which
has no subprocesses; the browser terminates its Web Worker instead.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .facts import Diagnostic, Severity
from .sandbox import DEFAULT_STEP_LIMIT, DEFAULT_TIME_LIMIT, RunResult

_MARKER = "\x00PYMENTOR-RESULT\x00"

# Runs in the child: -I isolates it from the environment and the current
# directory, so we put this package's parent on sys.path explicitly.
_CHILD = f"""
import json, sys
sys.path.insert(0, {str(Path(__file__).resolve().parents[1])!r})
from pymentor.sandbox import execute
job = json.loads(sys.stdin.read())
result = execute(job["source"], job["inputs"], step_limit=job["step_limit"],
                 time_limit=job["time_limit"])
sys.__stdout__.write({_MARKER!r} + json.dumps(result.to_dict()) + "\\n")
"""


def run_isolated(
    source: str,
    inputs: list[str] | None = None,
    *,
    step_limit: int = DEFAULT_STEP_LIMIT,
    time_limit: float = DEFAULT_TIME_LIMIT,
    hard_timeout: float | None = None,
) -> RunResult:
    """Like ``sandbox.execute``, but in a child process that is killed if it hangs."""
    job = {
        "source": source,
        "inputs": list(inputs or []),
        "step_limit": step_limit,
        "time_limit": time_limit,
    }
    hard_timeout = hard_timeout if hard_timeout is not None else time_limit * 2 + 5
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", _CHILD],
            input=json.dumps(job),
            capture_output=True,
            text=True,
            timeout=hard_timeout,
        )
    except subprocess.TimeoutExpired:
        return RunResult("", _killed(f"The program was stopped after {hard_timeout:g} seconds."))

    for line in reversed(completed.stdout.splitlines()):
        if line.startswith(_MARKER):
            return RunResult.from_dict(json.loads(line[len(_MARKER) :]))
    # The child died without reporting (for example, the learner killed it).
    return RunResult("", _killed("The program stopped unexpectedly.", completed.stderr))


def _killed(message: str, detail: str = "") -> Diagnostic:
    # We don't know which line was running, so the diagnostic says so.
    return Diagnostic(
        Severity.RUNTIME, "Timeout", message, line=1, data={"reason": "killed", "detail": detail}
    )
