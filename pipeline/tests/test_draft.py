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
