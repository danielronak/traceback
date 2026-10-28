"""The faithfulness checker for model output (D11).

Truth comes from tools, language from the model (principle 1). This module
checks that a piece of model text says nothing the engine didn't establish.
It is used three ways: as an evaluation metric, as the automatic judge for
preference tuning, and at runtime, where any text that fails is replaced by
the card's own wording.

The checks are deliberately simple and lexical, so they're fast enough to run
after every generation in the browser:

- **Line numbers** mentioned must be ones the facts mention, or a line whose
  code the same sentence quotes.
- **Code in backticks** may only use names that appear in the learner's code,
  the card, the fix, or Python itself.
- **Code blocks** must compile, and statements in backticks (`total = 0`)
  must be the learner's code, the card's or the fix's.
- **Error types** named (``NameError`` and so on) must be the actual error, or
  one the card itself names.
- **Early hints** must not give the fix away.
- **Length** stays within a limit per task.
"""

from __future__ import annotations

import ast
import builtins
import keyword
import re
import textwrap
from dataclasses import dataclass

from .facts import Finding

# Words per task: short enough to read on a card, long enough to explain.
WORD_LIMITS = {
    "explain": 120,
    "hint_level_1": 50,
    "hint_level_2": 60,
    "hint_level_3": 80,
    "why_followup": 150,
    "review": 120,
    "logic_error": 150,
}
EARLY_HINTS = ("hint_level_1", "hint_level_2")  # these must not reveal the fix

LINE_MENTION = re.compile(
    r"\blines?\s+(\d+(?:\s*(?:,|and|or|to|through|-|\u2013)\s*\d+)*)", re.IGNORECASE
)
NUMBER = re.compile(r"\d+")
BACKTICKS = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
FENCE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)
ERROR_TYPE = re.compile(r"\b([A-Z][A-Za-z]*(?:Error|Exception))\b")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
PYTHON_NAMES = frozenset(dir(builtins)) | frozenset(keyword.kwlist) | frozenset(keyword.softkwlist)


@dataclass(frozen=True)
class Problem:
    check: str  # line, name, code, error-type, leak, length, empty
    detail: str

    def __str__(self) -> str:
        return f"{self.check}: {self.detail}"


def check(text: str, finding: Finding, source: str, task: str) -> list[Problem]:
    """Everything in ``text`` that the facts don't support. Empty means grounded."""
    problems: list[Problem] = []
    if not text.strip():
        return [Problem("empty", "no text")]

    allowed = allowed_lines(finding)
    lines = source.splitlines()
    for sentence in SENTENCE.split(text):
        quoted = [_squash(span) for span in BACKTICKS.findall(sentence) if len(_squash(span)) > 1]
        for mention in LINE_MENTION.finditer(sentence):
            for number in map(int, NUMBER.findall(mention[1])):
                # Another line is fine when the sentence quotes what is really on it:
                # "you defined `year` on line 3". The code itself is a fact.
                shows = 1 <= number <= len(lines) and any(
                    q in _squash(lines[number - 1]) for q in quoted
                )
                if number not in allowed and not shows:
                    problems.append(Problem("line", f"mentions line {number}, not in the facts"))

    known = known_names(finding, source)
    for span in BACKTICKS.findall(text):
        for name in _names_in(span):
            if name not in known:
                problems.append(Problem("name", f"`{name}` isn't in the code, the card or Python"))

    for block in FENCE.findall(text):
        if not compiles(block):
            problems.append(Problem("code", "a code block doesn't compile"))

    # A statement in backticks (`total = 0`, `import math`) is a claim about what
    # the code is or should be: it must be the learner's, the card's or the fix's.
    sources = _squash(source + _card_text(finding) + (finding.fix.after if finding.fix else ""))
    for span in BACKTICKS.findall(text):
        if _is_statement(span) and _squash(span) not in sources:
            problems.append(
                Problem("code", f"`{span}` isn't the learner's code, the card or the fix")
            )

    card_text = _card_text(finding)
    for error_type in set(ERROR_TYPE.findall(text)):
        if error_type != finding.diagnostic.code and error_type not in card_text:
            problems.append(
                Problem("error-type", f"names {error_type}, but this is {finding.diagnostic.code}")
            )

    if task in EARLY_HINTS and finding.fix is not None:
        for fixed_line in finding.fix.after.splitlines():
            if fixed_line.strip() and _squash(fixed_line) in _squash(text):
                problems.append(Problem("leak", "an early hint shows the fixed code"))
                break

    words = len(text.split())
    if words > WORD_LIMITS.get(task, 150):
        problems.append(Problem("length", f"{words} words; {task} allows {WORD_LIMITS[task]}"))
    return problems


def is_grounded(text: str, finding: Finding, source: str, task: str) -> bool:
    return not check(text, finding, source, task)


def allowed_lines(finding: Finding) -> set[int]:
    """The line numbers the facts mention: the error's, any line-valued feature
    (an `if` header, the `input()` line, a loop's start), and the fix's lines."""
    d = finding.diagnostic
    lines = {d.line}
    if d.end_line:
        lines.add(d.end_line)
    for key, value in finding.features.items():
        if key.endswith("line") and isinstance(value, int) and not isinstance(value, bool):
            lines.add(value)
    if finding.fix is not None:
        changed = max(len(finding.fix.before.splitlines()), 1)
        lines.update(range(finding.fix.line, finding.fix.line + changed))
    return lines


def known_names(finding: Finding, source: str) -> set[str]:
    """Names the text may use in code: the learner's, the card's, the fix's and Python's."""
    names = set(IDENTIFIER.findall(source)) | set(IDENTIFIER.findall(_card_text(finding)))
    if finding.fix is not None:
        names |= set(IDENTIFIER.findall(finding.fix.after))
    return names | PYTHON_NAMES


STATEMENTS = (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Import, ast.ImportFrom, ast.Return)


def _is_statement(span: str) -> bool:
    try:
        tree = ast.parse(span.strip())
    except (SyntaxError, ValueError):
        return False
    return any(isinstance(node, STATEMENTS) for node in tree.body)


def compiles(block: str) -> bool:
    """Whether a code block is valid Python. A fix is often one line lifted from
    a larger program: indented (`    return total`), or a block header whose body
    follows in the learner's code (`for name in ages:`). Both count, as long as
    the line itself is correct."""
    source = textwrap.dedent(block).strip("\n")
    for candidate in (source, source + "\n    pass"):
        try:
            ast.parse(candidate)
            return True
        except (SyntaxError, ValueError):
            continue
    return False


def _names_in(span: str) -> list[str]:
    """Identifiers used as code in a backtick span (not words inside strings)."""
    try:
        tree = ast.parse(span.strip(), mode="exec")
    except SyntaxError:
        # Not a whole statement (`if x > 2`, `:`), so check its bare identifiers.
        without_strings = re.sub(r"(['\"]).*?\1", "", span)
        return IDENTIFIER.findall(without_strings)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.append(node.id)
        elif isinstance(node, ast.Attribute):
            found.append(node.attr)
        elif isinstance(node, ast.FunctionDef | ast.ClassDef):
            found.append(node.name)
    return found


def _card_text(finding: Finding) -> str:
    card = finding.card
    if card is None:
        return finding.diagnostic.message
    return "\n".join(
        [card.title, card.rule, card.why, card.exceptions, *card.hints, finding.diagnostic.message]
    )


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)
