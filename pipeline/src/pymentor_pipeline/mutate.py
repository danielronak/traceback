"""Bug mutators: each injects one realistic beginner mistake into a correct
program, at every place it can apply.

A mutator takes the source and returns ``Mutation`` objects, each a whole
broken program. Mutators never decide whether the result is an error, or which
one: the engine does that (principle 1). A mutation the engine has nothing to
say about is simply dropped by the generator.

Everything is deterministic: the same seed always gives the same mutations, so
the dataset can be rebuilt exactly.
"""

from __future__ import annotations

import ast
import io
import keyword
import random
import re
import tokenize
from collections.abc import Callable, Iterator
from dataclasses import dataclass

BLOCK_KEYWORDS = (
    "if",
    "elif",
    "else",
    "for",
    "while",
    "def",
    "class",
    "try",
    "except",
    "finally",
    "with",
)
TYPO_BUILTINS = ("print", "input", "len", "range", "int", "str", "sum", "float", "sorted")


@dataclass(frozen=True)
class Mutation:
    kind: str  # the mutator's name
    source: str  # the whole broken program
    line: int  # where the change was made (1-based)


Mutator = Callable[["Program"], Iterator[Mutation]]
MUTATORS: dict[str, Mutator] = {}


def mutator(fn: Mutator) -> Mutator:
    MUTATORS[fn.__name__] = fn
    return fn


class Program:
    """A seed program with its lines, tokens and syntax tree, for the mutators."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.lines = source.splitlines()
        self.tree = ast.parse(source)
        self.tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        self.names = {t.string for t in self.tokens if t.type == tokenize.NAME}

    def with_line(self, line: int, text: str) -> str:
        lines = list(self.lines)
        lines[line - 1] = text
        return "\n".join(lines) + "\n"

    def without_line(self, line: int) -> str:
        return "\n".join(self.lines[: line - 1] + self.lines[line:]) + "\n"

    def replace(self, line: int, start: int, end: int, text: str) -> str:
        old = self.lines[line - 1]
        return self.with_line(line, old[:start] + text + old[end:])

    def segment(self, node: ast.AST) -> str:
        return ast.get_source_segment(self.source, node) or ""

    def user_names(self) -> set[str]:
        """Names the program itself creates (variables, functions, parameters)."""
        found = {
            n.id
            for n in ast.walk(self.tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
        }
        found |= {
            n.name for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef | ast.ClassDef)
        }
        found |= {a.arg for a in ast.walk(self.tree) if isinstance(a, ast.arg)}
        return found - {"_", "self"}


def mutate(source: str, *, per_kind: int = 6, seed: str = "") -> list[Mutation]:
    """Every mutation of a program, at most ``per_kind`` of each kind.

    When a kind applies in more places than that, a sample is taken with a
    generator seeded by ``seed`` and the kind's name, so results are stable.
    """
    program = Program(source)
    results: list[Mutation] = []
    for name, fn in MUTATORS.items():
        found = list(dict.fromkeys(m for m in fn(program) if m.source != source))
        if len(found) > per_kind:
            found = random.Random(f"{seed}:{name}").sample(found, per_kind)
            found.sort(key=lambda m: m.line)
        results.extend(found)
    return results


def typo(word: str, rng: random.Random) -> str:
    """A plausible misspelling: a letter dropped, doubled or swapped, or a capital."""
    options = []
    if len(word) > 3:
        i = rng.randrange(1, len(word) - 1)
        options.append(word[:i] + word[i + 1 :])  # drop a letter
    if len(word) > 2:
        i = rng.randrange(0, len(word) - 1)
        if word[i] != word[i + 1]:
            options.append(word[:i] + word[i + 1] + word[i] + word[i + 2 :])  # swap two
    i = rng.randrange(0, len(word))
    options.append(word[: i + 1] + word[i] + word[i + 1 :])  # double a letter
    if word[0].islower():
        options.append(word[0].upper() + word[1:])  # a capital
    return rng.choice(options)


def _rng(program: Program, *parts: object) -> random.Random:
    return random.Random(f"{program.source}:{parts}")


def _code_tokens(program: Program) -> list[tokenize.TokenInfo]:
    skip = (
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.COMMENT,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
    )
    return [t for t in program.tokens if t.type not in skip]


# --- syntax mistakes --------------------------------------------------------------


@mutator
def drop_colon(program: Program) -> Iterator[Mutation]:
    """if x > 2:  ->  if x > 2"""
    tokens = program.tokens
    for i, tok in enumerate(tokens):
        if tok.string == ":" and tokens[i + 1].type in (tokenize.NEWLINE, tokenize.COMMENT):
            first = program.lines[tok.start[0] - 1].split()[0].rstrip(":(")
            if first in BLOCK_KEYWORDS:
                row, col = tok.start
                yield Mutation("drop_colon", program.replace(row, col, col + 1, ""), row)


@mutator
def assign_in_condition(program: Program) -> Iterator[Mutation]:
    """if x == 5:  ->  if x = 5:"""
    for node in ast.walk(program.tree):
        if isinstance(node, ast.If | ast.While) and isinstance(node.test, ast.Compare):
            line = node.test.lineno
            text = program.lines[line - 1]
            at = text.find("==", node.test.col_offset)
            if at >= 0:
                yield Mutation("assign_in_condition", program.replace(line, at, at + 2, "="), line)


@mutator
def dedent_body(program: Program) -> Iterator[Mutation]:
    """The first line of a block loses its indentation."""
    for node in ast.walk(program.tree):
        body = getattr(node, "body", None)
        if isinstance(node, ast.Module) or not isinstance(body, list) or not body:
            continue
        first = body[0]
        header = program.lines[node.lineno - 1]
        text = program.lines[first.lineno - 1]
        if first.lineno != node.lineno and first.lineno == first.end_lineno:
            indent = header[: len(header) - len(header.lstrip())]
            yield Mutation(
                "dedent_body", program.with_line(first.lineno, indent + text.lstrip()), first.lineno
            )


@mutator
def extra_indent(program: Program) -> Iterator[Mutation]:
    """A line that follows an ordinary line is indented further."""
    continues = (":", ",", "(", "[", "{")
    for i in range(1, len(program.lines)):
        before, line = program.lines[i - 1], program.lines[i]
        same_level = len(line) - len(line.lstrip()) == len(before) - len(before.lstrip())
        if (
            before.strip()
            and line.strip()
            and same_level
            and not before.rstrip().endswith(continues)
            and not line.lstrip().startswith(("else", "elif", "except", "finally"))
        ):
            yield Mutation("extra_indent", program.with_line(i + 1, "    " + line), i + 1)


@mutator
def unclose_bracket(program: Program) -> Iterator[Mutation]:
    """print(len(x))  ->  print(len(x)"""
    for number, text in enumerate(program.lines, start=1):
        code = text.split("#")[0].rstrip()
        if code.endswith(")") and code.count("(") == code.count(")") and code.count("(") >= 1:
            yield Mutation("unclose_bracket", program.with_line(number, code[:-1]), number)


@mutator
def extra_bracket(program: Program) -> Iterator[Mutation]:
    """print(x)  ->  print(x))"""
    for number, text in enumerate(program.lines, start=1):
        code = text.split("#")[0].rstrip()
        if code.endswith(")") and code.count("(") == code.count(")") and not code.endswith(":"):
            yield Mutation("extra_bracket", program.with_line(number, code + ")"), number)


@mutator
def mismatch_bracket(program: Program) -> Iterator[Mutation]:
    """[1, 2, 3]  ->  [1, 2, 3)"""
    for tok in _code_tokens(program):
        if tok.string == "]":
            row, col = tok.start
            yield Mutation("mismatch_bracket", program.replace(row, col, col + 1, ")"), row)


@mutator
def python2_print(program: Program) -> Iterator[Mutation]:
    """print(x)  ->  print x"""
    for node in program.tree.body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "print"
            and len(node.value.args) == 1
            and not node.value.keywords
            and node.lineno == node.end_lineno
        ):
            argument = program.segment(node.value.args[0])
            line = node.lineno
            indent = program.lines[line - 1][: node.col_offset]
            yield Mutation(
                "python2_print", program.with_line(line, f"{indent}print {argument}"), line
            )


@mutator
def unterminate_string(program: Program) -> Iterator[Mutation]:
    """print("hi")  ->  print("hi)"""
    for tok in _code_tokens(program):
        if tok.type == tokenize.STRING and tok.start[0] == tok.end[0] and tok.string[-1] in "'\"":
            if tok.string.startswith(("'''", '"""')):
                continue
            row, end = tok.end
            yield Mutation("unterminate_string", program.replace(row, end - 1, end, ""), row)


@mutator
def misspell_keyword(program: Program) -> Iterator[Mutation]:
    """while True:  ->  whlie True:"""
    rng = _rng(program, "keyword")
    for number, text in enumerate(program.lines, start=1):
        word = re.match(r"\s*(\w+)", text)
        if word and word[1] in (
            "if",
            "for",
            "while",
            "def",
            "return",
            "import",
            "elif",
            "else",
            "class",
        ):
            wrong = typo(word[1], rng)
            if wrong != word[1] and not keyword.iskeyword(wrong):
                yield Mutation(
                    "misspell_keyword",
                    program.replace(number, word.start(1), word.end(1), wrong),
                    number,
                )


@mutator
def def_without_brackets(program: Program) -> Iterator[Mutation]:
    """def greet():  ->  def greet:"""
    for node in ast.walk(program.tree):
        if isinstance(node, ast.FunctionDef) and not node.args.args:
            text = program.lines[node.lineno - 1]
            if "():" in text:
                yield Mutation(
                    "def_without_brackets",
                    program.with_line(node.lineno, text.replace("():", ":", 1)),
                    node.lineno,
                )


@mutator
def dedent_return(program: Program) -> Iterator[Mutation]:
    """A function's final `return` slips out of the function."""
    for node in program.tree.body:
        if isinstance(node, ast.FunctionDef) and isinstance(node.body[-1], ast.Return):
            line = node.body[-1].lineno
            if line == node.body[-1].end_lineno:
                yield Mutation(
                    "dedent_return", program.with_line(line, program.lines[line - 1].lstrip()), line
                )


# --- names ---------------------------------------------------------------------------


@mutator
def misspell_name(program: Program) -> Iterator[Mutation]:
    """print(total)  ->  print(totl)"""
    rng = _rng(program, "name")
    own = program.user_names()
    for node in ast.walk(program.tree):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in own
            and len(node.id) > 1
        ):
            wrong = typo(node.id, rng)
            if wrong not in program.names and not keyword.iskeyword(wrong):
                line = node.lineno
                yield Mutation(
                    "misspell_name",
                    program.replace(line, node.col_offset, node.end_col_offset, wrong),
                    line,
                )


@mutator
def misspell_builtin(program: Program) -> Iterator[Mutation]:
    """print(x)  ->  pritn(x)"""
    rng = _rng(program, "builtin")
    for node in ast.walk(program.tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in TYPO_BUILTINS
        ):
            wrong = typo(node.func.id, rng)
            if wrong not in program.names:
                f = node.func
                yield Mutation(
                    "misspell_builtin",
                    program.replace(f.lineno, f.col_offset, f.end_col_offset, wrong),
                    f.lineno,
                )


@mutator
def unquote_string(program: Program) -> Iterator[Mutation]:
    """print("hello")  ->  print(hello)"""
    for node in ast.walk(program.tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and re.fullmatch(r"[A-Za-z]{3,}", node.value)
            and node.value not in program.names
            and node.lineno == node.end_lineno
        ):
            yield Mutation(
                "unquote_string",
                program.replace(node.lineno, node.col_offset, node.end_col_offset, node.value),
                node.lineno,
            )


@mutator
def drop_import(program: Program) -> Iterator[Mutation]:
    """Remove `import math` but keep using it."""
    for node in program.tree.body:
        if isinstance(node, ast.Import) and node.lineno == node.end_lineno:
            yield Mutation("drop_import", program.without_line(node.lineno), node.lineno)


@mutator
def capitalise_variable(program: Program) -> Iterator[Mutation]:
    """total = 0 ... total  ->  Total = 0 ... Total (a style mistake)"""
    variables = {
        n.id
        for n in ast.walk(program.tree)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    }
    for name in sorted(variables - {"_"}):
        new = name[0].upper() + name[1:]
        if not name[0].islower() or new in program.names:
            continue
        uses = [
            tok
            for previous, tok in zip([None, *program.tokens], program.tokens, strict=False)
            if tok.type == tokenize.NAME
            and tok.string == name
            and (previous is None or previous.string != ".")
        ]
        lines = list(program.lines)
        for tok in reversed(uses):  # right to left keeps earlier columns valid
            row, col = tok.start
            lines[row - 1] = lines[row - 1][:col] + new + lines[row - 1][col + len(name) :]
        yield Mutation("capitalise_variable", "\n".join(lines) + "\n", uses[0].start[0])


# --- types, values and logic ------------------------------------------------------------


@mutator
def drop_conversion(program: Program) -> Iterator[Mutation]:
    """int(input())  ->  input();  str(n)  ->  n"""
    for node in ast.walk(program.tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("int", "str", "float")
            and len(node.args) == 1
            and node.lineno == node.end_lineno
        ):
            inner = program.segment(node.args[0])
            yield Mutation(
                "drop_conversion",
                program.replace(node.lineno, node.col_offset, node.end_col_offset, inner),
                node.lineno,
            )


@mutator
def off_by_one(program: Program) -> Iterator[Mutation]:
    """range(n)  <->  range(n + 1), and the same for a slice or index end."""
    for node in ast.walk(program.tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "range"
            and node.args
        ):
            stop = node.args[0] if len(node.args) == 1 else node.args[1]
            if stop.lineno != stop.end_lineno:
                continue
            text = program.segment(stop)
            changed = text[: -len(" + 1")] if text.endswith(" + 1") else f"{text} + 1"
            yield Mutation(
                "off_by_one",
                program.replace(stop.lineno, stop.col_offset, stop.end_col_offset, changed),
                stop.lineno,
            )


@mutator
def print_instead_of_return(program: Program) -> Iterator[Mutation]:
    """return answer  ->  print(answer)"""
    for node in ast.walk(program.tree):
        if isinstance(node, ast.FunctionDef):
            for statement in node.body:
                if (
                    isinstance(statement, ast.Return)
                    and statement.value is not None
                    and statement.lineno == statement.end_lineno
                ):
                    line = statement.lineno
                    indent = program.lines[line - 1][: statement.col_offset]
                    value = program.segment(statement.value)
                    yield Mutation(
                        "print_instead_of_return",
                        program.with_line(line, f"{indent}print({value})"),
                        line,
                    )


@mutator
def compare_flip(program: Program) -> Iterator[Mutation]:
    """>= becomes >, and < becomes <=: the classic boundary mistake."""
    swaps = {">=": ">", ">": ">=", "<=": "<", "<": "<="}
    for tok in _code_tokens(program):
        if tok.type == tokenize.OP and tok.string in swaps:
            row, col = tok.start
            yield Mutation(
                "compare_flip",
                program.replace(row, col, col + len(tok.string), swaps[tok.string]),
                row,
            )


@mutator
def drop_f_prefix(program: Program) -> Iterator[Mutation]:
    """f"Total: {total}"  ->  "Total: {total}" (style: a silent bug)"""
    for node in ast.walk(program.tree):
        if isinstance(node, ast.JoinedStr) and node.lineno == node.end_lineno:
            text = program.lines[node.lineno - 1]
            if text[node.col_offset : node.col_offset + 1] in "fF":
                yield Mutation(
                    "drop_f_prefix",
                    program.replace(node.lineno, node.col_offset, node.col_offset + 1, ""),
                    node.lineno,
                )
