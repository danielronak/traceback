"""The harness scores grounding, length and fixes, and the baseline is grounded."""

import csv
from pathlib import Path

from pymentor import Engine
from pymentor_pipeline import benchmark, evaluate
from pymentor_pipeline.baseline import template

V0 = Path(__file__).resolve().parents[2] / "benchmark" / "v0"
ITEMS = evaluate.items(benchmark.load(V0))
WITH_FIX = [i for i in ITEMS if i.task == "explain" and i.finding.fix is not None]


def _code(text):
    return f"Try this:\n```python\n{text}\n```"


def test_the_template_baseline_is_grounded_on_every_item():
    report = evaluate.score(ITEMS, evaluate.run_model(template, ITEMS))
    assert report["items"] == len(ITEMS) == 5 * len(benchmark.load(V0))
    assert report["overall"]["grounded"] == 1.0
    assert report["overall"]["with_code"] == 0


def test_the_engines_own_fixes_verify_and_the_broken_code_does_not():
    sample = WITH_FIX[::4]
    assert sample
    assert all(evaluate.fix_verifies(i, i.finding.fix.after) for i in sample)
    assert not any(evaluate.fix_verifies(i, i.finding.fix.before) for i in sample)


def test_fix_scores_count_only_outputs_with_code():
    sample = WITH_FIX[:10]
    outputs = [
        {"case": i.case, "task": i.task, "output": _code(i.finding.fix.after if n % 2 else "???")}
        for n, i in enumerate(sample)
    ]
    report = evaluate.score(sample, outputs)
    assert report["overall"]["with_code"] == 10
    assert report["overall"]["fix_ok"] == 0.5


def test_ungrounded_and_missing_outputs_are_caught():
    item = WITH_FIX[0]
    outputs = [{"case": item.case, "task": item.task, "output": "Look at line 999."}]
    report = evaluate.score([item, ITEMS[1]], outputs)
    assert report["overall"]["grounded"] == 0.0
    assert report["overall"]["problems"]["line"] == 1
    assert report["overall"]["missing"] == 1


def test_hand_scoring_sheet_has_a_sample_of_every_task(tmp_path):
    outputs = evaluate.run_model(template, ITEMS)
    rows = evaluate.hand_sheet(ITEMS, outputs, tmp_path / "sheet.csv", per_task=3)
    with (tmp_path / "sheet.csv").open(newline="") as file:
        sheet = list(csv.DictReader(file))
    assert len(sheet) == rows == 15
    assert {r["task"] for r in sheet} == {i.task for i in ITEMS}
    assert all(r["output"] and r["code"] and r["clarity_1_to_5"] == "" for r in sheet)


def test_models_load_by_name():
    assert evaluate.load_model("template") is template
    assert evaluate.load_model("pymentor_pipeline.baseline:template") is template


def test_a_fix_that_adds_a_line_verifies_when_the_model_shows_that_line():
    source = "w = 3\nc = 4\nprint(math.sqrt(w**2 + c**2))\n"
    finding = Engine().run(source).findings[0]
    assert finding.fix is not None and finding.fix.before == ""  # inserts `import math`
    item = evaluate.Item("c", "explain", "", finding, source, (), ())
    assert evaluate.fix_verifies(item, "import math")
    assert not evaluate.fix_verifies(item, "import maths")
