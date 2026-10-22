"""Small helpers for working with the learner's source text."""

from __future__ import annotations

import io
import tokenize

# The filename learner code is compiled under. Traceback frames with this
# filename belong to the learner; everything else is Python or a library.
LEARNER_FILENAME = "<learner>"
# The filename exercise test calls are compiled under.
TEST_FILENAME = "<test>"


def lines(source: str) -> list[str]:
    """The source split into lines, without line endings."""
    return source.splitlines()


def line_text(source: str, line: int) -> str:
    """The text of a 1-based line, or "" if it doesn't exist."""
    all_lines = lines(source)
    return all_lines[line - 1] if 1 <= line <= len(all_lines) else ""


def indentation(text: str) -> str:
    """The leading whitespace of a line."""
    return text[: len(text) - len(text.lstrip(" \t"))]


def replace_line(source: str, line: int, new_text: str) -> str:
    """Replace one 1-based line, keeping the source's trailing newline."""
    all_lines = lines(source)
    all_lines[line - 1] = new_text
    return join(all_lines, source)


def replace_span(source: str, line: int, col: int, end_col: int, new_text: str) -> str:
    """Replace columns [col, end_col) of a single line."""
    text = line_text(source, line)
    return replace_line(source, line, text[:col] + new_text + text[end_col:])


def join(all_lines: list[str], like: str) -> str:
    """Join lines back together, ending with a newline if ``like`` did."""
    text = "\n".join(all_lines)
    return text + "\n" if like.endswith("\n") else text


def tokens(source: str) -> list[tokenize.TokenInfo]:
    """Tokenize as far as possible; stop quietly at the first tokenizer error."""
    result: list[tokenize.TokenInfo] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            result.append(tok)
    except (tokenize.TokenError, SyntaxError):
        pass
    return result


def changed_region(old: str, new: str) -> tuple[int, str, str]:
    """The first changed line (1-based) and the changed text before and after."""
    a, b = lines(old), lines(new)
    start = 0
    while start < min(len(a), len(b)) and a[start] == b[start]:
        start += 1
    end_a, end_b = len(a), len(b)
    while end_a > start and end_b > start and a[end_a - 1] == b[end_b - 1]:
        end_a -= 1
        end_b -= 1
    return start + 1, "\n".join(a[start:end_a]), "\n".join(b[start:end_b])
