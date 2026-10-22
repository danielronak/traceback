"""The engine runs inside Pyodide, so it may import only the standard library (D1)."""

import ast
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "pymentor"


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_engine_imports_only_the_standard_library():
    allowed = set(sys.stdlib_module_names) | {"pymentor"}
    offenders = {
        f"{path.relative_to(PACKAGE)}: {name}"
        for path in PACKAGE.rglob("*.py")
        for name in _top_level_imports(path) - allowed
    }
    assert not offenders, f"non-stdlib imports in the engine: {sorted(offenders)}"
