"""Fine-tuning learns its targets, checkpoints, resumes, and feeds the harness."""

import json

import pytest
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


def _weights(folder):
    from transformers import AutoModelForCausalLM

    return {
        k: v.clone() for k, v in AutoModelForCausalLM.from_pretrained(folder).state_dict().items()
    }


def test_stepping_in_backward_trains_exactly_like_the_standard_loop(tiny_base, tiny_data, tmp_path):
    # Without clipping (the one place the two differ), every weight gets the same update.
    settings = {"max_steps": 6, "optimizer": "adamw", "max_grad_norm": 0, "lr": 1e-3}
    train(config(tiny_base, tiny_data, tmp_path / "a", **settings), log=lambda _: None)
    train(
        config(tiny_base, tiny_data, tmp_path / "b", step_in_backward=True, **settings),
        log=lambda _: None,
    )
    a, b = _weights(tmp_path / "a" / "last"), _weights(tmp_path / "b" / "last")
    base = _weights(tiny_base)
    assert any(not a[k].equal(base[k]) for k in base)  # it did train
    for name in a:
        assert (a[name] - b[name]).abs().max() < 1e-5, name


def test_stepping_in_backward_resumes_and_refuses_what_it_cannot_do(tiny_base, tiny_data, tmp_path):
    settings = {"step_in_backward": True, "optimizer": "adafactor", "save_every": 5}
    train(config(tiny_base, tiny_data, tmp_path, max_steps=5, **settings), log=lambda _: None)
    summary = train(
        config(tiny_base, tiny_data, tmp_path, max_steps=8, **settings),
        resume=True,
        log=lambda _: None,
    )
    assert summary["steps"] == 8
    with pytest.raises(ValueError, match="grad_accum"):
        train(config(tiny_base, tiny_data, tmp_path / "x", grad_accum=4, step_in_backward=True))


def test_answer_only_scoring_gives_the_models_own_loss(tiny_base, tiny_data):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from pymentor_training.data import add_special_tokens, collate, encode, load_drafts
    from pymentor_training.sft import answer_loss

    tokenizer = AutoTokenizer.from_pretrained(tiny_base)
    model = AutoModelForCausalLM.from_pretrained(tiny_base)
    add_special_tokens(tokenizer, model)
    rows = [encode(tokenizer, e, 2048) for e in load_drafts(tiny_data / "drafts-train.jsonl")[:3]]
    batch = collate(rows, tokenizer.pad_token_id)
    assert model.config.model_type == "llama"
    assert abs(answer_loss(model, batch).item() - model(**batch).loss.item()) < 1e-5
