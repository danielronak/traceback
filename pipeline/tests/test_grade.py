"""The grader judges drafts like a person would, and is checked against people."""

import json
import shutil

from pymentor_pipeline import draft, grade, review
from pymentor_pipeline.generate import read_jsonl


def card_teacher(system, prompt_text):
    section = prompt_text.split("<|card|>", 1)[1].split("\n<|", 1)[0]
    return section.splitlines()[-1]


def strict_grader(system, prompt_text):
    """Calls every hint bad, everything else good."""
    assert system == grade.RUBRIC and "The tutor's answer:" in prompt_text
    return "BAD: says too much" if "<|task|>hint_level" in prompt_text else "GOOD"


def _drafted(tmp_path, small_dataset):
    data = tmp_path / "data"
    shutil.copytree(small_dataset[0], data)
    for name in ("drafts-train.jsonl", "rejected-train.jsonl"):
        (data / name).unlink(missing_ok=True)
    draft.draft(data, "train", card_teacher, name="fake", limit=20, log=lambda _: None)
    return data


def test_replies_are_read_as_verdicts():
    def says(text):
        return grade.grade_one(lambda s, p: text, "facts<|response|>", "answer<|end|>")

    assert says("GOOD") == ("good", "")
    assert says("**BAD**: gives the fix away\nmore") == ("bad", "gives the fix away")
    assert says("I think it's fine") == ("unclear", "I think it's fine")
    assert says("") == ("unclear", "")
    assert says(None) == ("unclear", "")
    # Reasoning first, or a verdict later on, still counts.
    assert says("The code has `Sam` on line 2.\nVerdict: **BAD** - gives it away") == (
        "bad",
        "gives it away",
    )
    assert says("Checking each claim... all true. GOOD") == ("good", "")


def test_grading_covers_every_draft_once_and_resumes(tmp_path, small_dataset):
    data = _drafted(tmp_path, small_dataset)
    drafts = read_jsonl(data / "drafts-train.jsonl")
    calls = []

    def grader(system, prompt_text):
        calls.append(prompt_text)
        return strict_grader(system, prompt_text)

    result = grade.grade(data, "train", grader, name="judge", log=lambda _: None)
    assert result["graded"] == len(drafts) == len(calls)
    grade.grade(data, "train", grader, name="judge", log=lambda _: None)
    assert len(calls) == len(drafts)  # nothing left to grade
    hints = sum(d["task"].startswith("hint") for d in drafts)
    assert result["good"] == round((len(drafts) - hints) / len(drafts), 3)
    shown = []
    review.report(data, "train", show=shown.append)
    assert any(line.startswith("grader:") for line in shown)
    assert any("=== GRADED BAD hint_level" in line for line in shown)


def test_calibration_measures_agreement_with_people(tmp_path, small_dataset):
    data = _drafted(tmp_path, small_dataset)
    drafts = read_jsonl(data / "drafts-train.jsonl")
    # People marked the hints bad, and one explanation too.
    verdicts = ["bad" if d["task"].startswith("hint") else "good" for d in drafts]
    explain = next(i for i, d in enumerate(drafts) if not d["task"].startswith("hint"))
    verdicts[explain] = "bad"
    with (data / "reviews-train.jsonl").open("w", encoding="utf-8") as file:
        for row, verdict in zip(drafts, verdicts, strict=True):
            file.write(
                json.dumps({"case": row["case"], "task": row["task"], "verdict": verdict}) + "\n"
            )
    result = grade.calibrate([data], strict_grader)
    bad = verdicts.count("bad")
    assert result["answers"] == len(drafts)
    assert result["agreement"] == round((len(drafts) - 1) / len(drafts), 3)
    assert result["catches_bad"] == round((bad - 1) / bad, 3)
    assert result["bad_is_right"] == 1.0
