"""The tutor model's input format, defined once (D10).

Data generation, evaluation and in-browser inference all build prompts with
``build``. A drifted newline between training and serving would quietly
degrade the model, so nothing else may assemble these strings.

A prompt is a sequence of sections, each opened by a special token::

    <|task|>hint_level_1
    <|level|>beginner
    <|error|>SyntaxError line 2: expected ':'
    <|card|>Missing colon on line 2
    Every line that starts a block (...) ends with a colon.
    Python groups code by indentation ...
    <|hint|>Look at the very end of line 2.
    <|code|>
    1 scores = [72, 85, 90]
    2 if len(scores) > 2
    3     print("Enough scores")
    <|response|>

The model writes its answer after ``<|response|>`` and ends it with
``<|end|>``. Every fact in the prompt comes from the engine (principle 1).
"""

from __future__ import annotations

import ast

from .facts import Finding, Severity

PROMPT_VERSION = 1

# The jobs one model does (vision.md, "The model's job"), told apart by the
# task token. `explain` covers logic errors too when a card exists; `logic_error`
# is for failing tests that no card explains, and `review` for working code.
TASKS = (
    "explain",
    "hint_level_1",
    "hint_level_2",
    "hint_level_3",
    "why_followup",
    "review",
    "logic_error",
)
LEVELS = ("beginner", "intermediate")
SPECIAL_TOKENS = (
    "<|task|>",
    "<|level|>",
    "<|error|>",
    "<|card|>",
    "<|hint|>",
    "<|fix|>",
    "<|question|>",
    "<|code|>",
    "<|response|>",
    "<|end|>",
)
WINDOW_RADIUS = 3  # lines of context either side of the error
MAX_FUNCTION_LINES = 30  # include the whole enclosing function if it's this short
DEFAULT_QUESTION = "Why does Python work this way?"


def build(
    finding: Finding,
    source: str,
    task: str,
    *,
    level: str = "beginner",
    question: str | None = None,
) -> str:
    """The model input for one finding and one task, ending at ``<|response|>``."""
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}; expected one of {TASKS}")
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}; expected one of {LEVELS}")
    d = finding.diagnostic
    card = finding.card
    parts = [
        f"<|task|>{task}",
        f"<|level|>{level}",
        f"<|error|>{d.code} line {d.line}: {d.message}",
    ]
    if card is None:
        parts.append("<|card|>none")
    else:
        parts.append(f"<|card|>{card.title}\n{card.rule}\n{card.why}")
        if task.startswith("hint_level_"):
            rung = int(task.rsplit("_", 1)[1])
            if rung <= len(card.hints):
                parts.append(f"<|hint|>{card.hints[rung - 1]}")
    if finding.fix is not None and task in ("explain", "hint_level_3"):
        parts.append(f"<|fix|>before:\n{finding.fix.before}\nafter:\n{finding.fix.after}")
    if task == "why_followup":
        parts.append(f"<|question|>{question or DEFAULT_QUESTION}")
    parts.append("<|code|>\n" + format_window(code_window(source, d.line)))
    parts.append("<|response|>")
    return "\n".join(parts)


def target(text: str) -> str:
    """A training target: the answer text, ended the way the model must end it."""
    return text.strip() + "<|end|>"


def tasks_for(finding: Finding) -> list[str]:
    """The tasks worth generating for a finding."""
    if finding.card is None:
        return ["logic_error"] if finding.diagnostic.severity is Severity.LOGIC else ["explain"]
    return ["explain", "hint_level_1", "hint_level_2", "hint_level_3", "why_followup"]


def code_window(source: str, line: int) -> list[tuple[int, str]]:
    """Real line numbers and text around a line, widened to its whole function
    when that function is short."""
    lines = source.splitlines()
    if not lines:
        return []
    line = min(max(line, 1), len(lines))
    start, end = max(1, line - WINDOW_RADIUS), min(len(lines), line + WINDOW_RADIUS)
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        tree = None
    if tree is not None:
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.lineno <= line <= (node.end_lineno or node.lineno)
        ]
        if functions:
            inner = max(functions, key=lambda n: n.lineno)
            if (inner.end_lineno or inner.lineno) - inner.lineno + 1 <= MAX_FUNCTION_LINES:
                start, end = min(start, inner.lineno), max(end, inner.end_lineno or end)
    return [(n, lines[n - 1]) for n in range(start, end + 1)]


def format_window(window: list[tuple[int, str]]) -> str:
    return "\n".join(f"{number} {text}" for number, text in window)
