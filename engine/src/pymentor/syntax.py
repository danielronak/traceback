"""Syntax errors, straight from Python's own compiler."""

from __future__ import annotations

from .facts import Diagnostic, Severity
from .source import LEARNER_FILENAME


def check_syntax(source: str) -> Diagnostic | None:
    """Compile the source; return the first syntax error, or None if it compiles.

    Python stops at the first syntax error, and so do we (D6): fixing the first
    error first is also how Python itself asks to be read.
    """
    try:
        compile(source, LEARNER_FILENAME, "exec", dont_inherit=True)
    except SyntaxError as error:  # includes IndentationError and TabError
        return from_syntax_error(error)
    except ValueError as error:  # e.g. "source code string cannot contain null bytes"
        return Diagnostic(Severity.SYNTAX, "SyntaxError", str(error), line=1)
    return None


def from_syntax_error(error: SyntaxError) -> Diagnostic:
    line = error.lineno or 1
    # SyntaxError offsets are 1-based; ours are 0-based. Python uses 0 or -1
    # for "no end position", which we turn into None.
    col = max((error.offset or 1) - 1, 0)
    end_line = error.end_lineno if error.end_lineno and error.end_lineno > 0 else None
    end_col = error.end_offset - 1 if error.end_offset and error.end_offset > 0 else None
    if end_col is not None and end_line == line and end_col < col:
        end_col = None
    return Diagnostic(
        severity=Severity.SYNTAX,
        code=type(error).__name__,
        message=error.msg,
        line=line,
        col=col,
        end_line=end_line,
        end_col=end_col,
    )
