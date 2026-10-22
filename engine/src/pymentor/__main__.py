"""Command line: try the engine on a file.

python -m pymentor check my_program.py
python -m pymentor check my_program.py --run --input 14 --input Ada
python -m pymentor check my_program.py --run --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import Engine, Report
from .facts import Finding, Severity
from .isolated import run_isolated

LABELS = {
    Severity.SYNTAX: "Won't run",
    Severity.RUNTIME: "Crashed",
    Severity.STYLE: "Style",
    Severity.LOGIC: "Wrong answer",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pymentor", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check a Python file")
    check.add_argument("file", type=Path)
    check.add_argument("--run", action="store_true", help="also run the program")
    check.add_argument(
        "--input", action="append", default=[], help="an answer for input(); repeatable"
    )
    check.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    source = args.file.read_text(encoding="utf-8")
    # Learner programs run in a killable subprocess here, so a hang can't
    # freeze the terminal.
    engine = Engine(runner=run_isolated)
    report = engine.run(source, args.input) if args.run else engine.check(source)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(_describe(report))
    return 1 if report.blocking else 0


def _describe(report: Report) -> str:
    parts = []
    if report.ran:
        parts.append("--- output ---\n" + (report.stdout or "(nothing printed)\n"))
    if not report.findings:
        parts.append("No problems found.")
    for finding in report.findings:
        parts.append(_describe_finding(finding))
    return "\n".join(parts)


def _describe_finding(finding: Finding) -> str:
    d = finding.diagnostic
    label = LABELS[d.severity]
    if finding.card is None:
        return f"[{label}] line {d.line}: {d.code}: {d.message}\n  (no rule card yet)\n"
    card = finding.card
    lines = [f"[{label}] line {d.line}: {card.title}"]
    if finding.fix:
        for before in finding.fix.before.splitlines() or [""]:
            lines.append(f"  - {before}")
        for after in finding.fix.after.splitlines():
            lines.append(f"  + {after}")
    lines.append(f"  Rule: {card.rule}")
    lines.append(f"  Why:  {card.why}")
    lines.extend(f"  Hint {n}: {hint}" for n, hint in enumerate(card.hints, start=1))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
