"""Feature extractors: facts about *why* an error happened.

Python reports *what* went wrong (``NameError: name 'totl' is not defined``).
Teaching needs the cause: was it a typo of a name the learner created, a
misspelled builtin, a missing import, a name used before it was assigned?
Each extractor computes named facts that rule cards put conditions on (D2).
This module is the only place that cause-detection code lives; the teaching
itself stays in the cards.

Every feature is plain data (str, int, bool or None). None means "not
applicable", so a card condition ``similar_name = true`` fails on it.
"""

from __future__ import annotations

import ast
import builtins
import difflib
import keyword
import re
import sys
import tokenize
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .facts import Diagnostic
from .source import line_text, tokens

Features = dict[str, Any]


@dataclass(frozen=True)
class Context:
    source: str
    diagnostic: Diagnostic
    tree: ast.Module | None  # None when the source doesn't compile

    @property
    def line_text(self) -> str:
        return line_text(self.source, self.diagnostic.line)

    def message_match(self, pattern: str) -> re.Match[str] | None:
        return re.search(pattern, self.diagnostic.message)


_EXTRACTORS: dict[str, list[Callable[[Context], Features]]] = {}


def extractor(*codes: str):
    """Register a function that extracts features for diagnostics with these codes."""

    def register(fn: Callable[[Context], Features]) -> Callable[[Context], Features]:
        for code in codes:
            _EXTRACTORS.setdefault(code, []).append(fn)
        return fn

    return register


def extract(diagnostic: Diagnostic, source: str) -> Features:
    """All features for one diagnostic: its facts, then cause-specific extras."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        tree = None
    context = Context(source, diagnostic, tree)
    features: Features = {
        "code": diagnostic.code,
        "message": diagnostic.message,
        "line": diagnostic.line,
        "col": diagnostic.col,
        "line_text": context.line_text.strip(),
    }
    features.update({k: v for k, v in diagnostic.data.items() if k != "frames"})
    for fn in _EXTRACTORS.get(diagnostic.code, []):
        features.update(fn(context))
    return features


# --- shared helpers ----------------------------------------------------------

PUBLIC_BUILTINS = frozenset(n for n in dir(builtins) if not n.startswith("_"))
STDLIB_MODULES = frozenset(m for m in sys.stdlib_module_names if not m.startswith("_"))
# Methods that change an object in place and return None.
INPLACE_METHODS = frozenset(
    {"sort", "reverse", "append", "extend", "insert", "remove", "clear", "update", "add"}
)


@dataclass(frozen=True)
class Binding:
    name: str
    line: int
    scope: str  # "<module>" or the enclosing function's name
    node: ast.AST


def bindings(tree: ast.Module) -> list[Binding]:
    """Every place a name is created, with the scope it is created in."""
    found: list[Binding] = []

    class Visitor(ast.NodeVisitor):
        scope = "<module>"

        def add(self, name: str, node: ast.AST) -> None:
            found.append(Binding(name, node.lineno, self.scope, node))

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Store | ast.Del):
                self.add(node.id, node)

        def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self.add(node.name, node)
            for decorator in node.decorator_list:
                self.visit(decorator)
            outer, self.scope = self.scope, node.name
            for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
                self.add(arg.arg, arg)
            for arg in (node.args.vararg, node.args.kwarg):
                if arg:
                    self.add(arg.arg, arg)
            for statement in node.body:
                self.visit(statement)
            self.scope = outer

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.add(node.name, node)
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import | ast.ImportFrom) -> None:
            for alias in node.names:
                self.add((alias.asname or alias.name).split(".")[0], node)

        visit_ImportFrom = visit_Import

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if node.name:
                self.add(node.name, node)
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def enclosing_function(tree: ast.Module, line: int) -> ast.FunctionDef | None:
    """The innermost function whose body contains this line."""
    best = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.lineno < line <= (node.end_lineno or node.lineno)
            and (best is None or node.lineno > best.lineno)
        ):
            best = node
    return best


def node_at(tree: ast.Module, diagnostic: Diagnostic, *types: type) -> ast.AST | None:
    """The node of one of these types that starts exactly where Python pointed."""
    for node in ast.walk(tree):
        if (
            isinstance(node, types)
            and node.lineno == diagnostic.line
            and node.col_offset == diagnostic.col
            and (diagnostic.end_col is None or node.end_col_offset == diagnostic.end_col)
        ):
            return node
    return None


def closest(word: str, candidates: set[str] | frozenset[str], cutoff: float = 0.75) -> str | None:
    """The most similar candidate, ignoring case, or None if nothing is close."""
    if not word or not candidates:
        return None
    lowered = {c.lower(): c for c in sorted(candidates)}
    matches = difflib.get_close_matches(word.lower(), list(lowered), n=1, cutoff=cutoff)
    return lowered[matches[0]] if matches else None


def latest_binding_before(tree: ast.Module, name: str, line: int) -> Binding | None:
    before = [b for b in bindings(tree) if b.name == name and b.line <= line]
    return max(before, key=lambda b: b.line) if before else None


def is_input_call(node: ast.AST | None) -> bool:
    return (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "input"
    )


def _assigned_value(binding: Binding, tree: ast.Module) -> ast.AST | None:
    """The value assigned in ``name = value``, if that is how the name was bound."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and binding.node in node.targets:
            return node.value
    return None


# --- syntax errors -----------------------------------------------------------


@extractor("SyntaxError")
def _syntax(context: Context) -> Features:
    features: Features = {}
    first_word = re.match(r"\s*(\w+)", context.line_text)
    if first_word:
        features["keyword"] = first_word[1]
    match = context.message_match(r"^unterminated string literal")
    if match:
        text = context.line_text
        quote = text[context.diagnostic.col] if context.diagnostic.col < len(text) else None
        features["quote"] = quote if quote in ("'", '"') else None
    match = context.message_match(r"^'([(\[{])' was never closed")
    if match:
        features["bracket"] = match[1]
        features["closer"] = {"(": ")", "[": "]", "{": "}"}[match[1]]
    match = context.message_match(r"^unmatched '([)\]}])'")
    if match:
        features["bracket"] = match[1]
    match = context.message_match(
        r"^closing parenthesis '([)\]}])' does not match opening parenthesis '([(\[{])'"
    )
    if match:
        features["closer"], features["opener"] = match[1], match[2]
        features["expected_closer"] = {"(": ")", "[": "]", "{": "}"}[match[2]]
    if context.diagnostic.message == "invalid syntax":
        features["keyword_as_name"] = _keyword_assigned(context)
    return features


def _keyword_assigned(context: Context) -> str | None:
    """`class = 3`: a keyword used as a variable name."""
    line_tokens = [
        t
        for t in tokens(context.line_text.strip() + "\n")
        if t.type not in (tokenize.INDENT, tokenize.DEDENT)
    ]
    if (
        len(line_tokens) >= 2
        and line_tokens[0].string in keyword.kwlist
        and line_tokens[1].string == "="
    ):
        return line_tokens[0].string
    return None


_HEADER_KINDS = {"function definition": "def", "class definition": "class"}


@extractor("IndentationError")
def _indentation(context: Context) -> Features:
    match = context.message_match(r"^expected an indented block after (.+?) on line (\d+)")
    if not match:
        return {}
    header = match[1]
    kind = re.match(r"'(\w+)' statement", header)
    return {
        "header_line": int(match[2]),
        "header_kind": kind[1] if kind else _HEADER_KINDS.get(header, header),
    }


# --- names -------------------------------------------------------------------


@extractor("NameError")
def _name_error(context: Context) -> Features:
    name = context.diagnostic.data.get("name")
    if not name or context.tree is None:
        return {}
    tree, line = context.tree, context.diagnostic.line
    all_bindings = bindings(tree)
    user_names = {b.name for b in all_bindings}
    of_name = [b for b in all_bindings if b.name == name]

    here = enclosing_function(tree, line)
    scope = here.name if here else "<module>"
    local_elsewhere = [b for b in of_name if b.scope not in (scope, "<module>")]

    node = node_at(tree, context.diagnostic, ast.Name)
    in_print = False
    if node is not None:
        for parent in ast.walk(tree):
            if (
                isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Name)
                and parent.func.id == "print"
                and node in parent.args
            ):
                in_print = True

    similar = closest(name, user_names - {name})
    builtin = None if similar else closest(name, PUBLIC_BUILTINS - {name}, cutoff=0.8)
    module = name if name in STDLIB_MODULES and name not in user_names else None
    return {
        "similar_name": similar,
        "builtin_name": builtin,
        "module": module,
        "defined_anywhere": bool(of_name),
        "defined_later": any(b.line > line and b.scope in (scope, "<module>") for b in of_name),
        "defined_in_function": local_elsewhere[0].scope if local_elsewhere else None,
        "in_print": in_print,
        "word_like": name.isalpha(),
    }


@extractor("UnboundLocalError")
def _unbound_local(context: Context) -> Features:
    match = context.message_match(r"local variable '(\w+)'")
    if not match or context.tree is None:
        return {}
    name = match[1]
    function = enclosing_function(context.tree, context.diagnostic.line)
    return {
        "name": name,
        "function": function.name if function else None,
        "global_defined": any(
            b.name == name and b.scope == "<module>" for b in bindings(context.tree)
        ),
    }


# --- types -------------------------------------------------------------------


@extractor("TypeError")
def _type_error(context: Context) -> Features:
    features: Features = {}
    tree, diagnostic = context.tree, context.diagnostic

    match = context.message_match(r'^can only concatenate (\w+) \(not "(\w+)"\) to \1')
    if match:
        features.update(operator="+", left_type=match[1], right_type=match[2])
    match = context.message_match(r"^unsupported operand type\(s\) for (.+?): '(\w+)' and '(\w+)'")
    if match:
        features.update(operator=match[1], left_type=match[2], right_type=match[3])
    if "left_type" in features and tree is not None:
        features.update(_from_input(tree, diagnostic))

    for pattern in (
        r"^'(\w+)' object is not callable",
        r"^'(\w+)' object is not subscriptable",
        r"^'(\w+)' object is not iterable",
        r"^'(\w+)' object does not support item assignment",
    ):
        match = context.message_match(pattern)
        if match:
            features["obj_type"] = match[1]

    if tree is not None and context.message_match(r"is not callable"):
        call = node_at(tree, diagnostic, ast.Call)
        if call is not None and isinstance(call.func, ast.Name):
            name = call.func.id
            features["called_name"] = name
            features["shadowed_builtin"] = name in PUBLIC_BUILTINS and any(
                b.name == name for b in bindings(tree)
            )
    if context.message_match(r"is not subscriptable"):
        features["is_function"] = features.get("obj_type") in (
            "function",
            "builtin_function_or_method",
            "method",
        )
        node = node_at(tree, diagnostic, ast.Subscript) if tree is not None else None
        if node is not None:
            features["subscript_value"] = ast.get_source_segment(context.source, node.value)
    if tree is not None and context.message_match(r"is not iterable"):
        features["in_for"] = any(
            isinstance(node, ast.For)
            and node.iter.lineno == diagnostic.line
            and node.iter.col_offset == diagnostic.col
            for node in ast.walk(tree)
        )

    match = context.message_match(
        r"^(\w+)\(\) missing (\d+) required (?:positional|keyword-only) arguments?: (.+)$"
    )
    if match:
        features.update(function=match[1], missing_count=int(match[2]), missing_args=match[3])
    return features


def _from_input(tree: ast.Module, diagnostic: Diagnostic) -> Features:
    """Is one side of this operation a variable that holds text from input()?"""
    operation = node_at(tree, diagnostic, ast.BinOp, ast.AugAssign)
    if operation is None:
        return {}
    # Search the whole expression: in `"Next: " + age + 1` the failing `+` is
    # between `"Next: " + age` and `1`, but the cause is still `age`.
    names = [n for n in ast.walk(operation) if isinstance(n, ast.Name)]
    if isinstance(operation, ast.AugAssign) and isinstance(operation.target, ast.Name):
        names.insert(0, operation.target)
    for name in names:
        binding = latest_binding_before(tree, name.id, diagnostic.line)
        if binding and is_input_call(_assigned_value(binding, tree)):
            return {"input_name": name.id, "input_line": binding.line}
    return {}


# --- values, lookups and attributes ------------------------------------------


@extractor("IndexError")
def _index_error(context: Context) -> Features:
    match = context.message_match(r"^(\w+) index out of range")
    features: Features = {"container_type": match[1] if match else None}
    if context.tree is not None:
        node = node_at(context.tree, context.diagnostic, ast.Subscript)
        if node is not None:
            features["index_text"] = ast.get_source_segment(context.source, node.slice)
            features["container_text"] = ast.get_source_segment(context.source, node.value)
    return features


@extractor("ValueError")
def _value_error(context: Context) -> Features:
    match = context.message_match(r"^invalid literal for (int)\(\) with base 10: (.+)$")
    match = match or context.message_match(r"^could not convert string to (float): (.+)$")
    if not match:
        return {}
    value = match[2]
    return {
        "target_type": match[1],
        "value": value,
        "value_is_decimal": bool(re.fullmatch(r"'\s*-?\d+\.\d*\s*'", value)),
        "value_is_empty": value in ("''", '""'),
    }


@extractor("AttributeError")
def _attribute_error(context: Context) -> Features:
    features: Features = {}
    match = context.message_match(r"^'(\w+)' object has no attribute '(\w+)'")
    match = match or context.message_match(r"^(module) '\w+' has no attribute '(\w+)'")
    if match:
        features.update(obj_type=match[1], attribute=match[2])
    suggestion = context.message_match(r"Did you mean: '(\w+)'\?")
    features["python_suggestion"] = suggestion[1] if suggestion else None

    if features.get("obj_type") == "NoneType" and context.tree is not None:
        node = node_at(context.tree, context.diagnostic, ast.Attribute)
        if node is not None and isinstance(node.value, ast.Name):
            binding = latest_binding_before(context.tree, node.value.id, context.diagnostic.line)
            value = _assigned_value(binding, context.tree) if binding else None
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and value.func.attr in INPLACE_METHODS
            ):
                features.update(
                    none_name=node.value.id,
                    inplace_method=value.func.attr,
                    inplace_line=binding.line,
                )
    return features


@extractor("ModuleNotFoundError")
def _module_not_found(context: Context) -> Features:
    match = context.message_match(r"^No module named '([\w.]+)'")
    if not match:
        return {}
    module = match[1]
    return {
        "module": module,
        "similar_module": closest(module, STDLIB_MODULES - {module}, cutoff=0.8),
    }


@extractor("RecursionError")
def _recursion(context: Context) -> Features:
    frames = context.diagnostic.data.get("frames", [])
    repeated = max(frames, key=lambda f: f["repeats"], default=None)
    return {"function": repeated["function"] if repeated else None}


# --- loops that never end ----------------------------------------------------


@extractor("Timeout")
def _timeout(context: Context) -> Features:
    if context.tree is None or context.diagnostic.data.get("reason") == "killed":
        return {}
    line = context.diagnostic.line
    loops = [
        node
        for node in ast.walk(context.tree)
        if isinstance(node, ast.While | ast.For)
        and node.lineno <= line <= (node.end_lineno or node.lineno)
    ]
    if not loops:
        return {}
    loop = max(loops, key=lambda n: n.lineno)  # the innermost loop
    features: Features = {
        "loop_line": loop.lineno,
        "loop_kind": "while" if isinstance(loop, ast.While) else "for",
        "unchanged_names": None,
    }
    if isinstance(loop, ast.While):
        condition_names = sorted(
            {n.id for n in ast.walk(loop.test) if isinstance(n, ast.Name)} - PUBLIC_BUILTINS
        )
        changed = _names_changed_in(loop.body)
        if condition_names and not set(condition_names) & changed:
            features["unchanged_names"] = ", ".join(condition_names)
    return features


def _names_changed_in(body: list[ast.stmt]) -> set[str]:
    """Names assigned in these statements, or whose methods are called (`items.pop()`)."""
    changed: set[str] = set()
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                changed.add(node.id)
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
            ):
                changed.add(node.func.value.id)
            elif isinstance(node, ast.Global | ast.Nonlocal):
                changed.update(node.names)
    return changed


# --- exercises: test calls and logic errors ---------------------------------------


@extractor("NameError")
def _missing_test_function(context: Context) -> Features:
    """The exercise calls a function the learner hasn't written (or named differently)."""
    data = context.diagnostic.data
    if not data.get("in_test_call") or data.get("name") != data.get("test_function"):
        return {}
    return {"missing_test_function": data["test_function"]}


@extractor("test-failed")
def _test_failed(context: Context) -> Features:
    data = context.diagnostic.data
    printed = data.get("printed", "").strip()
    returned_none = data.get("actual") == "None" and data.get("expected") != "None"
    features: Features = {
        "returned_none": returned_none,
        "printed_expected": returned_none
        and bool(printed)
        and printed.splitlines()[-1].strip() == data.get("expected_str"),
        "text_not_number": data.get("actual_type") == "str"
        and data.get("expected_type") in ("int", "float")
        and data.get("actual_str") == data.get("expected_str"),
        "off_by_one": False,
        "has_return": None,
    }
    if data.get("expected_type") == data.get("actual_type") == "int":
        features["off_by_one"] = abs(int(data["expected_str"]) - int(data["actual_str"])) == 1
    if context.tree is not None:
        function = next(
            (
                n
                for n in ast.walk(context.tree)
                if isinstance(n, ast.FunctionDef) and n.name == data.get("function")
            ),
            None,
        )
        if function is not None:
            features["has_return"] = any(
                isinstance(n, ast.Return) and n.value is not None for n in ast.walk(function)
            )
    return features


@extractor("wrong-output")
def _wrong_output(context: Context) -> Features:
    data = context.diagnostic.data
    printed = ast.literal_eval(data["actual"]) if "actual" in data else ""
    inputs = [i.strip() for i in data.get("inputs", [])]
    features: Features = {
        "nothing_printed": printed == "",
        # "3" and "4" printed as "34": answers from input() joined as text.
        "joined_inputs": len(inputs) >= 2
        and all(re.fullmatch(r"-?\d+", i) for i in inputs)
        and printed.strip() == "".join(inputs),
    }
    if context.tree is not None:
        defined = [n.name for n in context.tree.body if isinstance(n, ast.FunctionDef)]
        called = {
            n.func.id
            for n in ast.walk(context.tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        never_called = [name for name in defined if name not in called]
        features["uncalled_function"] = never_called[0] if never_called else None
    return features
