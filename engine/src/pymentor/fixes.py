"""Deterministic fix generators, and the rule that decides whether a fix works.

A card names its generator in ``fix``, optionally with an argument naming the
feature that holds the replacement: ``fix = "replace_name:similar_name"``.
A generator returns candidate programs, most likely first. The engine keeps
the first candidate that ``verify`` accepts and drops the rest (D3, D4).
"""

from __future__ import annotations

import ast
import re
import tokenize
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .facts import Diagnostic, Severity
from .source import indentation, join, line_text, lines, replace_line, replace_span, tokens
from .style import check_style
from .syntax import check_syntax


@dataclass(frozen=True)
class FixContext:
    source: str
    diagnostic: Diagnostic
    features: dict[str, Any]
    arg: str | None = None  # the part after ':' in the card's fix spec

    @property
    def line(self) -> str:
        return line_text(self.source, self.diagnostic.line)

    @property
    def value(self) -> Any:
        """The feature named by the fix argument (e.g. the replacement name)."""
        return self.features.get(self.arg) if self.arg else None

    def tree(self) -> ast.Module | None:
        try:
            return ast.parse(self.source)
        except (SyntaxError, ValueError):
            return None


Generator = Callable[[FixContext], list[str]]
_GENERATORS: dict[str, Generator] = {}


def generator(fn: Generator) -> Generator:
    _GENERATORS[fn.__name__] = fn
    return fn


def has_generator(spec: str) -> bool:
    return spec.partition(":")[0] in _GENERATORS


def candidates(
    spec: str, source: str, diagnostic: Diagnostic, features: dict[str, Any]
) -> list[str]:
    name, _, arg = spec.partition(":")
    context = FixContext(source, diagnostic, features, arg or None)
    try:
        found = _GENERATORS[name](context)
    except (ValueError, IndexError, KeyError, AttributeError, TypeError):
        return []  # a generator that can't apply produces nothing; never crash the UI
    unique = []
    for candidate in found:
        if candidate != source and candidate not in unique:
            unique.append(candidate)
    return unique


# --- verification ------------------------------------------------------------

Runner = Callable[[str, list[str]], Any]  # (source, inputs) -> sandbox.RunResult


def verify(original: Diagnostic, fixed: str, run: Runner, inputs: list[str]) -> bool:
    """Does the fixed program remove this error without a new one at or before its line?

    This is deliberately not "the program is now correct": fixing one error
    often reveals the next, further down, and that's fine.
    """
    syntax_error = check_syntax(fixed)
    if original.severity is Severity.SYNTAX:
        return syntax_error is None or syntax_error.line > original.line
    if syntax_error is not None:
        return False
    if original.severity is Severity.STYLE:
        return not any(
            d.code == original.code and d.line == original.line and d.data == original.data
            for d in check_style(ast.parse(fixed))
        )
    result = run(fixed, inputs)
    return result.diagnostic is None or result.diagnostic.line > original.line


# --- syntax fixes ------------------------------------------------------------


@generator
def insert_colon(ctx: FixContext) -> list[str]:
    col = ctx.diagnostic.col
    text = ctx.line
    code, comment = _split_comment(text)
    return [
        # At the end of the code, before any comment; Python's column can sit
        # after trailing spaces, which would give `range(3)  :# comment`.
        replace_line(ctx.source, ctx.diagnostic.line, code.rstrip() + ":" + comment),
        replace_line(ctx.source, ctx.diagnostic.line, text[:col] + ":" + text[col:]),
    ]


@generator
def assign_to_equals(ctx: FixContext) -> list[str]:
    d = ctx.diagnostic
    for tok in tokens(ctx.line.strip() + "\n"):
        offset = len(indentation(ctx.line))
        start = tok.start[1] + offset
        if tok.string == "=" and d.col <= start < (d.end_col or len(ctx.line)):
            return [replace_span(ctx.source, d.line, start, start + 1, "==")]
    return []


@generator
def indent_line(ctx: FixContext) -> list[str]:
    header = line_text(ctx.source, ctx.features["header_line"])
    body = indentation(header) + "    " + ctx.line.lstrip()
    return [replace_line(ctx.source, ctx.diagnostic.line, body)]


@generator
def dedent_line(ctx: FixContext) -> list[str]:
    all_lines = lines(ctx.source)
    previous = next((t for t in reversed(all_lines[: ctx.diagnostic.line - 1]) if t.strip()), "")
    return [
        replace_line(ctx.source, ctx.diagnostic.line, indentation(previous) + ctx.line.lstrip())
    ]


@generator
def expand_tabs(ctx: FixContext) -> list[str]:
    def expanded(width: int) -> str:
        result = []
        for text in lines(ctx.source):
            lead = indentation(text)
            result.append(lead.replace("\t", " " * width) + text[len(lead) :])
        return join(result, ctx.source)

    return [expanded(4), expanded(8)]


@generator
def close_string(ctx: FixContext) -> list[str]:
    quote = ctx.features["quote"]
    text = ctx.line.rstrip()
    # Most often the quote is missing just before closing brackets: print('hi)
    trailing = re.search(r"[)\]},:]*$", text)
    at = trailing.start() if trailing else len(text)
    return [
        replace_line(ctx.source, ctx.diagnostic.line, text[:at] + quote + text[at:]),
        replace_line(ctx.source, ctx.diagnostic.line, text + quote),
    ]


@generator
def close_bracket(ctx: FixContext) -> list[str]:
    code, comment = _split_comment(ctx.line)
    closer = ctx.features["closer"]
    return [replace_line(ctx.source, ctx.diagnostic.line, code.rstrip() + closer + comment)]


@generator
def remove_bracket(ctx: FixContext) -> list[str]:
    col = ctx.diagnostic.col
    if ctx.line[col : col + 1] != ctx.features["bracket"]:
        return []
    return [replace_span(ctx.source, ctx.diagnostic.line, col, col + 1, "")]


@generator
def swap_bracket(ctx: FixContext) -> list[str]:
    col = ctx.diagnostic.col
    if ctx.line[col : col + 1] != ctx.features["closer"]:
        return []
    return [
        replace_span(ctx.source, ctx.diagnostic.line, col, col + 1, ctx.features["expected_closer"])
    ]


@generator
def print_call(ctx: FixContext) -> list[str]:
    code, comment = _split_comment(ctx.line)
    match = re.match(r"^(\s*)print\s+(.+?)\s*$", code)
    if not match:
        return []
    return [replace_line(ctx.source, ctx.diagnostic.line, f"{match[1]}print({match[2]}){comment}")]


# --- name and attribute fixes -------------------------------------------------


@generator
def replace_name(ctx: FixContext) -> list[str]:
    """Swap the name Python pointed at for the feature named by the argument."""
    d, name, new = ctx.diagnostic, ctx.features["name"], ctx.value
    if not new or ctx.line[d.col : d.end_col] != name:
        return []
    return [replace_span(ctx.source, d.line, d.col, d.end_col, new)]


@generator
def quote_name(ctx: FixContext) -> list[str]:
    d, name = ctx.diagnostic, ctx.features["name"]
    if ctx.line[d.col : d.end_col] != name:
        return []
    return [replace_span(ctx.source, d.line, d.col, d.end_col, f'"{name}"')]


@generator
def add_import(ctx: FixContext) -> list[str]:
    all_lines = lines(ctx.source)
    tree = ctx.tree()
    statement = f"import {ctx.features['module']}"
    if tree is None:
        return []
    imports = [n for n in tree.body if isinstance(n, ast.Import | ast.ImportFrom)]
    at = imports[-1].end_lineno if imports else _first_code_line(tree, all_lines) - 1
    return [join([*all_lines[:at], statement, *all_lines[at:]], ctx.source)]


@generator
def replace_attribute(ctx: FixContext) -> list[str]:
    d, attribute, new = ctx.diagnostic, ctx.features["attribute"], ctx.value
    if not new or d.end_col is None or d.end_line != d.line:
        return []
    start = d.end_col - len(attribute)
    if ctx.line[start : d.end_col] != attribute:
        return []
    return [replace_span(ctx.source, d.line, start, d.end_col, new)]


@generator
def replace_module(ctx: FixContext) -> list[str]:
    module, new = ctx.features["module"], ctx.value
    match = re.search(rf"\b{re.escape(module)}\b", ctx.line)
    if not new or not match:
        return []
    return [replace_span(ctx.source, ctx.diagnostic.line, match.start(), match.end(), new)]


# --- type fixes ----------------------------------------------------------------


@generator
def str_right_operand(ctx: FixContext) -> list[str]:
    """'Age: ' + age  ->  'Age: ' + str(age)"""
    node = _node_at(ctx, ast.BinOp)
    if node is None:
        return []
    return [_wrap(ctx, node.right, "str")]


@generator
def int_input(ctx: FixContext) -> list[str]:
    """age = input('Age? ')  ->  age = int(input('Age? '))"""
    tree = ctx.tree()
    line = ctx.features["input_line"]
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "input"
            and node.lineno == line
        ):
            return [_wrap(ctx, node, "int")]
    return []


@generator
def wrap_range(ctx: FixContext) -> list[str]:
    """for i in 5:  ->  for i in range(5):"""
    tree = ctx.tree()
    d = ctx.diagnostic
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and (node.iter.lineno, node.iter.col_offset) == (
            d.line,
            d.col,
        ):
            return [_wrap(ctx, node.iter, "range")]
    return []


@generator
def brackets_to_call(ctx: FixContext) -> list[str]:
    """len[word]  ->  len(word)"""
    node = _node_at(ctx, ast.Subscript)
    if node is None or node.lineno != node.end_lineno:
        return []
    value = ast.get_source_segment(ctx.source, node.value)
    index = ast.get_source_segment(ctx.source, node.slice)
    return [
        replace_span(
            ctx.source, node.lineno, node.col_offset, node.end_col_offset, f"{value}({index})"
        )
    ]


# --- style fixes -----------------------------------------------------------------


@generator
def rename(ctx: FixContext) -> list[str]:
    """Rename every use of a name, leaving attributes (`obj.Name`) alone."""
    old, new = ctx.features["name"], ctx.value
    all_tokens = tokens(ctx.source)
    if not new or any(t.type == tokenize.NAME and t.string == new for t in all_tokens):
        return []  # the new name is taken; renaming would merge two variables
    edits = []
    previous = None
    for tok in all_tokens:
        if (
            tok.type == tokenize.NAME
            and tok.string == old
            and not (previous and previous.string == ".")
        ):
            edits.append(tok)
        if tok.type not in (tokenize.NL, tokenize.COMMENT):
            previous = tok
    all_lines = lines(ctx.source)
    for tok in reversed(edits):  # right to left keeps earlier columns valid
        row, col = tok.start
        text = all_lines[row - 1]
        all_lines[row - 1] = text[:col] + new + text[col + len(old) :]
    return [join(all_lines, ctx.source)]


@generator
def compare_with_is(ctx: FixContext) -> list[str]:
    """x == None  ->  x is None"""
    d = ctx.diagnostic
    op = ctx.features["op"]
    replacement = "is" if op == "==" else "is not"
    text = ctx.line
    for tok in tokens(text.strip() + "\n"):
        start = tok.start[1] + len(indentation(text))
        if (
            tok.string == op
            and d.col <= start
            and (d.end_line != d.line or start < (d.end_col or len(text)))
        ):
            return [replace_span(ctx.source, d.line, start, start + len(op), replacement)]
    return []


@generator
def drop_bool_compare(ctx: FixContext) -> list[str]:
    """done == True  ->  done;  done == False  ->  not done"""
    node = _node_at(ctx, ast.Compare)
    if node is None or node.lineno != node.end_lineno:
        return []
    left = ast.get_source_segment(ctx.source, node.left)
    positive = (ctx.features["op"] == "==") == (ctx.features["value"] == "True")
    simple = isinstance(node.left, ast.Name | ast.Attribute | ast.Call | ast.Subscript)
    new = left if positive else f"not {left}" if simple else f"not ({left})"
    return [replace_span(ctx.source, node.lineno, node.col_offset, node.end_col_offset, new)]


# --- helpers -----------------------------------------------------------------------


def _node_at(ctx: FixContext, kind: type) -> Any:
    tree = ctx.tree()
    d = ctx.diagnostic
    for node in ast.walk(tree):
        if isinstance(node, kind) and (node.lineno, node.col_offset) == (d.line, d.col):
            return node
    return None


def _wrap(ctx: FixContext, node: ast.AST, function: str) -> str:
    if node.lineno != node.end_lineno:
        raise ValueError("multi-line expression")
    segment = ast.get_source_segment(ctx.source, node)
    return replace_span(
        ctx.source, node.lineno, node.col_offset, node.end_col_offset, f"{function}({segment})"
    )


def _split_comment(text: str) -> tuple[str, str]:
    """Split a line into code and a trailing comment (with its leading spaces)."""
    for tok in tokens(text.strip() + "\n"):
        if tok.type == tokenize.COMMENT:
            col = tok.start[1] + len(indentation(text))
            code = text[:col]
            stripped = code.rstrip()
            return stripped, text[len(stripped) :]
    return text, ""


def _first_code_line(tree: ast.Module, all_lines: list[str]) -> int:
    """Where an import should go: after a module docstring and leading comments."""
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        return tree.body[0].end_lineno + 1
    for number, text in enumerate(all_lines, start=1):
        if text.strip() and not text.lstrip().startswith("#"):
            return number
    return 1
