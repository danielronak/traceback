"""Drafting holds the teacher to the tutor's own bar, and resumes cleanly."""

import json

import pytest

from pymentor_pipeline import draft, review, teachers
from pymentor_pipeline.generate import read_jsonl


@pytest.fixture(scope="module")
def data(small_dataset):
    return small_dataset[0]


def card_teacher(system, prompt_text):
    """Echo the card's own hint or rule: always grounded."""
    for tag in ("<|hint|>", "<|card|>"):
        if tag in prompt_text:
            section = prompt_text.split(tag, 1)[1].split("\n<|", 1)[0]
            return section.splitlines()[-1] if tag == "<|card|>" else section
    return None


def test_the_system_prompt_states_every_tasks_word_limit():
    system = draft.system_prompt()
    assert "hint_level_1 (at most 50 words)" in system and "UK English" in system


def test_grounded_drafts_are_kept_and_the_rest_rejected_with_reasons(data):
    def teacher(system, prompt_text):
        return (
            "See line 999." if "hint_level_1" in prompt_text else card_teacher(system, prompt_text)
        )

    tally = draft.draft(data, "val", teacher, name="fake", log=lambda _: None)
    assert tally["accepted"] and tally["rejected"]
    for row in read_jsonl(data / "drafts-val.jsonl"):
        assert row["target"].endswith("<|end|>") and row["prompt"].endswith("<|response|>")
    rejected = read_jsonl(data / "rejected-val.jsonl")
    assert all(r["task"] == "hint_level_1" for r in rejected)
    assert all(any(reason.startswith("line:") for reason in r["reasons"]) for r in rejected)

    # A second run has nothing left to do.
    assert draft.draft(data, "val", teacher, name="fake", log=lambda _: None) == {}


def test_code_that_isnt_a_working_fix_is_rejected(data):
    def teacher(system, prompt_text):
        return "Try this:\n```python\nprint(\n```" if "<|task|>explain" in prompt_text else None

    draft.draft(data, "test", teacher, name="fake", limit=20, log=lambda _: None)
    reasons = [r["reasons"] for r in read_jsonl(data / "rejected-test.jsonl")]
    assert any(any(x.startswith(("fix:", "code:")) for x in r) for r in reasons)
    assert ["declined"] in reasons


def test_offline_outputs_are_judged_the_same_way(data):
    examples = read_jsonl(data / "examples-train.jsonl")[:4]
    outputs = [(e["case"], e["task"], card_teacher("", e["prompt"])) for e in examples]
    tally = draft.accept_outputs(data, "train", outputs, name="batch")
    assert sum(tally.values()) == 4


def test_review_records_verdicts_and_summarises(data):
    answers = iter(["y", "n", "too wordy", "x", "s", "q"])
    shown = []
    tally = review.review(data, "val", sample=10, ask=lambda _: next(answers), show=shown.append)
    assert tally == {"good": 1, "bad": 1, "skip": 1}
    assert any(line.startswith(">>> ") for line in shown)
    notes = [json.loads(line)["note"] for line in (data / "reviews-val.jsonl").open()]
    assert "too wordy" in notes
    assert review.summary(data, "val")["good"] == 0.5


def test_the_local_teacher_talks_to_a_server_on_this_machine():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            reply = {
                "choices": [{"message": {"content": "Look at line 2."}, "finish_reason": "stop"}]
            }
            data = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        teach = teachers.local_teacher(url, model="tiny")
        assert teach("system text", "prompt text") == "Look at line 2."
    finally:
        server.shutdown()
    assert seen[0]["model"] == "tiny"
    assert [m["role"] for m in seen[0]["messages"]] == ["system", "user"]


def test_teachers_must_be_local():
    for url in ("https://api.example.com/v1/chat/completions", "http://10.0.0.5:8080/v1"):
        with pytest.raises(ValueError, match="locally"):
            teachers.local_teacher(url)


def test_drafting_order_is_balanced_across_cards():
    examples = [
        {"case": f"{card}{n}", "task": "explain", "card": card}
        for card, many in (("a", 9), ("b", 3))
        for n in range(many)
    ]
    ordered = draft.balanced(examples)
    assert sorted(e["case"] for e in ordered) == sorted(e["case"] for e in examples)
    assert [e["card"] for e in ordered[:6]] == ["a", "b"] * 3
    assert draft.balanced(examples) == ordered  # stable, so runs resume the same way


def test_limit_is_a_total_so_rerunning_resumes(tmp_path, small_dataset):
    import shutil

    data = tmp_path / "data"
    shutil.copytree(small_dataset[0], data)
    for name in ("drafts-train.jsonl", "rejected-train.jsonl"):
        (data / name).unlink(missing_ok=True)
    calls = []

    def teacher(system, prompt_text):
        calls.append(prompt_text)
        return card_teacher(system, prompt_text)

    draft.draft(data, "train", teacher, name="fake", limit=6, log=lambda _: None)
    draft.draft(data, "train", teacher, name="fake", limit=6, log=lambda _: None)
    assert len(calls) == 6  # the second run found the 6 already done
    draft.draft(data, "train", teacher, name="fake", limit=9, log=lambda _: None)
    assert len(calls) == 9


def _item_with_fix(data, task):
    from pymentor_pipeline.records import finding_from_record

    cases = {c["id"]: c for c in read_jsonl(data / "cases-train.jsonl")}
    for example in read_jsonl(data / "examples-train.jsonl"):
        case = cases[example["case"]]
        if example["task"] == task and case["finding"]["fix"]:
            return draft._item(case, example), finding_from_record(case["finding"]).fix
    raise AssertionError(f"no {task} example with a fix")


def test_judge_rejects_code_the_task_or_facts_do_not_allow(small_dataset):
    data = small_dataset[0]
    item, fix = _item_with_fix(data, "hint_level_3")
    good = f"Change it to this:\n```python\n{fix.after}\n```"
    assert draft.judge(good, item) == []
    before_after = f"Change\n```python\n{fix.before}\n```\nto\n```python\n{fix.after}\n```"
    assert "code: more than one code block" in draft.judge(before_after, item)

    hint, fix = _item_with_fix(data, "hint_level_1")
    assert "code: hint_level_1 shows no code" in draft.judge(f"```python\n{fix.after}\n```", hint)


def test_report_shows_counts_reasons_and_examples(data):
    def teacher(system, prompt_text):
        return (
            "See line 999." if "hint_level_1" in prompt_text else card_teacher(system, prompt_text)
        )

    draft.draft(data, "val", teacher, name="fake", log=lambda _: None)  # a no-op if done already
    lines = []
    review.report(data, "val", show=lines.append)
    text = "\n".join(lines)
    assert text.startswith("ACCEPTED ")
    assert "rejection reasons:" in text and "=== ACCEPTED" in text
    if "'bad'" in text:  # the review test marked one answer bad, with a note
        assert "=== REVIEWED BAD" in text


def test_the_worked_example_passes_every_check_the_teacher_faces():
    from pymentor import Engine
    from pymentor_pipeline.evaluate import Item

    finding = Engine().check(draft.EXAMPLE_SOURCE).findings[0]
    assert finding.card.id == "missing-colon" and finding.fix is not None
    for task, answer in draft.EXAMPLE_ANSWERS.items():
        item = Item("example", task, "", finding, draft.EXAMPLE_SOURCE, (), ())
        assert draft.judge(answer, item) == [], task
    system = draft.system_prompt()
    assert "if len(scores) > 2:" in system and "[hint_level_1]" in system


def test_drafting_refuses_data_from_an_older_engine(tmp_path, small_dataset):
    import shutil

    data = tmp_path / "data"
    shutil.copytree(small_dataset[0], data)
    draft.require_fresh(data)  # made by this engine
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    manifest["engine"] = "0" * 16
    (data / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="generate"):
        draft.draft(data, "train", card_teacher, name="fake", limit=1, log=lambda _: None)
