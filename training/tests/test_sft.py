"""Fine-tuning learns its targets, checkpoints, resumes, and feeds the harness."""

import json

from conftest import ITEMS, config, drafts

from pymentor_pipeline import evaluate
from pymentor_training.infer import Tutor
from pymentor_training.sft import train


def test_training_memorises_a_handful_of_targets(trained):
    out, summary = trained
    log = [json.loads(line) for line in (out / "log.jsonl").open()]
    assert len(log) == summary["steps"] == 120
    assert log[-1]["loss"] < log[0]["loss"] / 5
    assert summary["best_val_loss"] is not None
    for name in ("config.json", "summary.json", "best/config.json", "last/trainer.pt"):
        assert (out / name).exists(), name


def test_the_trained_tutor_answers_and_stops_at_end(trained, tiny_data):
    out, _ = trained
    tutor = Tutor(out / "last", device="cpu")
    row = json.loads((tiny_data / "drafts-train.jsonl").open().readline())
    answer = tutor.generate(row["prompt"])
    assert answer == row["target"].removesuffix("<|end|>").strip()


def test_resume_continues_from_the_last_checkpoint(tiny_base, tiny_data, tmp_path):
    train(config(tiny_base, tiny_data, tmp_path, max_steps=20, save_every=10), log=lambda _: None)
    lines = []
    summary = train(
        config(tiny_base, tiny_data, tmp_path, max_steps=30, save_every=10),
        resume=True,
        log=lines.append,
    )
    assert any("resumed at step 20" in line for line in lines)
    assert summary["steps"] == 30
    steps = [json.loads(line)["step"] for line in (tmp_path / "log.jsonl").open()]
    assert steps == list(range(1, 31))


def test_low_memory_options_train_too(tiny_base, tiny_data, tmp_path):
    summary = train(
        config(
            tiny_base,
            tiny_data,
            tmp_path,
            max_steps=4,
            optimizer="adafactor",
            dtype="bf16",
            gradient_checkpointing=True,
        ),
        log=lambda _: None,
    )
    assert summary["steps"] == 4


def test_the_harness_scores_a_trained_tutor(trained):
    out, _ = trained
    tutor = Tutor(out / "best", device="cpu", max_new_tokens=40)
    todo = [i for i in ITEMS if i.task == "hint_level_1"][:3]
    report = evaluate.score(todo, evaluate.run_model(tutor, todo))
    assert report["items"] == 3 and report["overall"]["missing"] == 0
    assert report["overall"]["ms_p50"] > 0
    assert len(drafts(todo)) == 3
