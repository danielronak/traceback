"""Style checks: code that works but doesn't read like Python.

A deliberately small set of AST rules, chosen for beginners rather than
completeness (D5). Each rule code has a matching rule card.
"""

from __future__ import annotations

import ast
import re

from .facts import Diagnostic, Severity

SNAKE_CASE = re.compile(r"^_*[a-z][a-z0-9_]*$")
UPPER_CASE = re.compile(r"^_*[A-Z][A-Z0-9_]*$")
CAP_WORDS = re.compile(r"^_*[A-Z][a-zA-Z0-9]*$")

# Builtins beginners most often overwrite by accident. Shadowing anything else
# (`id`, `type`, `vars`) is common enough in real code that flagging it would nag.
SHADOWED_BUILTINS = frozenset(
    {
        "list", "dict", "set", "tuple", "str", "int", "float", "bool",
        "sum", "max", "min", "len", "input", "print", "range", "sorted",
        "open", "round", "abs", "map", "filter", "zip", "any", "all",
    }
)  # fmt: skip


def check_style(tree: ast.Module) -> list[Diagnostic]:
    checker = _StyleChecker()
    checker.visit(tree)
    return sorted(checker.found, key=lambda d: (d.line, d.col))


def to_snake_case(name: str) -> str:
    """`myTotal` -> `my_total`, `Total` -> `total`, `HTTPCode` -> `http_code`."""
    prefix = name[: len(name) - len(name.lstrip("_"))]
    core = name.lstrip("_")
    core = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", core)
    core = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", core)
    return prefix + core.lower()


def to_cap_words(name: str) -> str:
    """`dog` -> `Dog`, `my_dog` -> `MyDog`, `myDog` -> `MyDog`."""
    prefix = name[: len(name) - len(name.lstrip("_"))]
    parts = [p for p in name.lstrip("_").split("_") if p]
    return prefix + "".join(p[0].upper() + p[1:] for p in parts)


class _StyleChecker(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found: list[Diagnostic] = []
        self._reported: set[tuple[str, str]] = set()
        self._depth = 0  # >0 inside a function or class body

    def _report(self, node: ast.AST, code: str, message: str, **data: object) -> None:
        key = (code, str(data.get("name", (node.lineno, node.col_offset))))
        if key in self._reported:
            return  # one finding per name is enough
        self._reported.add(key)
        self.found.append(
            Diagnostic(
                Severity.STYLE,
                code,
                message,
                line=node.lineno,
                col=node.col_offset,
                end_line=node.end_lineno,
                end_col=node.end_col_offset,
                data=dict(data),
            )
        )

    # --- names -----------------------------------------------------------

    def _check_binding(self, node: ast.AST, name: str) -> None:
        if name in SHADOWED_BUILTINS:
            self._report(node, "builtin-shadowed", f"'{name}' is the name of a built-in", name=name)
        elif not SNAKE_CASE.match(name) and not UPPER_CASE.match(name):
            self._report(
                node,
                "naming-variable",
                f"Variable name '{name}' is not snake_case",
                name=name,
                suggested_name=to_snake_case(name),
            )

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self._check_binding(node, node.id)

    def visit_arg(self, node: ast.arg) -> None:
        self._check_binding(node, node.arg)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        name = node.name
        if not (name.startswith("__") and name.endswith("__")) and not SNAKE_CASE.match(name):
            self._report(
                _name_span(node, name),
                "naming-function",
                f"Function name '{name}' is not snake_case",
                name=name,
                suggested_name=to_snake_case(name),
            )
        elif name in SHADOWED_BUILTINS and self._depth == 0:
            self._report(
                _name_span(node, name),
                "builtin-shadowed",
                f"'{name}' is the name of a built-in",
                name=name,
            )
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not CAP_WORDS.match(node.name):
            self._report(
                _name_span(node, node.name),
                "naming-class",
                f"Class name '{node.name}' is not CapWords",
                name=node.name,
                suggested_name=to_cap_words(node.name),
            )
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    # --- comparisons -----------------------------------------------------

    def visit_Compare(self, node: ast.Compare) -> None:
        if len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq | ast.NotEq):
            right = node.comparators[0]
            op = "==" if isinstance(node.ops[0], ast.Eq) else "!="
            if isinstance(right, ast.Constant) and right.value is None:
                self._report(
                    node, "compare-none", f"Comparison to None with '{op}'", op=op, value="None"
                )
            elif isinstance(right, ast.Constant) and isinstance(right.value, bool):
                self._report(
                    node,
                    "compare-bool",
                    f"Comparison to {right.value} with '{op}'",
                    op=op,
                    value=str(right.value),
                )
        self.generic_visit(node)


class _Span:
    """A position-only stand-in node, for pointing at a def/class name."""

    def __init__(self, line: int, col: int, end_col: int) -> None:
        self.lineno = self.end_lineno = line
        self.col_offset, self.end_col_offset = col, end_col


def _name_span(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, name: str) -> _Span:
    # ast positions cover the whole statement; the name follows the keyword.
    keyword = "class" if isinstance(node, ast.ClassDef) else "def"
    if isinstance(node, ast.AsyncFunctionDef):
        keyword = "async def"
    col = node.col_offset + len(keyword) + 1
    return _Span(node.lineno, col, col + len(name))
