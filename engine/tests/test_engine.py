import json
import time

from pymentor import Engine, Severity
from pymentor.isolated import run_isolated

ENGINE = Engine(step_limit=20_000)

# The program from the design doc's mockup.
MOCKUP = (
    'scores = [72, 85, 90]\nif len(scores) > 2\n    print("Enough scores")\nTotal = sum(scores)\n'
)


def test_design_doc_mockup():
    report = ENGINE.check(MOCKUP)
    red, blue = report.findings
    assert (red.diagnostic.severity, red.diagnostic.line, red.card.id) == (
        Severity.SYNTAX,
        2,
        "missing-colon",
    )
    assert (red.fix.before, red.fix.after) == ("if len(scores) > 2", "if len(scores) > 2:")
    assert (blue.diagnostic.severity, blue.diagnostic.line, blue.card.id) == (
        Severity.STYLE,
        4,
        "naming-variable",
    )
    assert blue.fix is None  # style fixes wait until the file compiles
    # Once the colon is in, the style finding gets its own fix.
    [blue] = ENGINE.check(red.fix.source).findings
    assert blue.fix.after == "total = sum(scores)"


def test_check_never_runs_the_code():
    started = time.monotonic()
    report = ENGINE.check("while True:\n    print('side effect')\n")
    assert report.findings == [] and not report.ran
    assert time.monotonic() - started < 1


def test_run_reports_output_and_runtime_finding():
    report = ENGINE.run("age = input('Age? ')\nprint(age + 1)\n", ["14"])
    assert report.ran and report.stdout == "Age? 14\n"
    assert report.blocking.card.id == "input-is-string"
    assert report.blocking.fix.after == "age = int(input('Age? '))"


def test_findings_are_ordered_blocking_first():
    report = ENGINE.run("Total = 1\nprint(1/0)\n")
    assert [f.diagnostic.severity for f in report.findings] == [Severity.RUNTIME, Severity.STYLE]


def test_error_without_a_card_is_low_confidence():
    finding = ENGINE.run("raise RuntimeError('boom')\n").blocking
    assert finding.card is None and finding.confidence == "low"


def test_report_serialises_to_json_for_the_browser():
    report = ENGINE.run(MOCKUP.replace("> 2", "> 2:"))
    data = json.loads(json.dumps(report.to_dict()))
    assert data["findings"][0]["card"]["id"] == "naming-variable"
    assert data["findings"][0]["diagnostic"]["severity"] == "style"


def test_engine_can_run_learner_code_in_a_subprocess():
    engine = Engine(runner=run_isolated)
    assert engine.run("y = totl + 1\n").blocking.card.id == "name-undefined"
