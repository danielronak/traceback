"""A tiny model and tokenizer built on the spot (no downloads), and drafts to
train them on. They test the code paths, not the quality of any real model."""

import json
from pathlib import Path

import pytest
from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers
from transformers import LlamaConfig, LlamaForCausalLM, PreTrainedTokenizerFast

from pymentor_pipeline import benchmark, evaluate
from pymentor_pipeline.baseline import template
from pymentor_training.sft import Config, train

REPO = Path(__file__).resolve().parents[2]
ITEMS = evaluate.items(benchmark.load(REPO / "benchmark" / "v0"))


def drafts(items):
    """Draft rows, using the template's text as the target."""
    return [
        {"case": i.case, "task": i.task, "prompt": i.prompt, "target": template(i) + "<|end|>"}
        for i in items
    ]


@pytest.fixture(scope="session")
def tiny_base(tmp_path_factory):
    """A 2-layer Llama with a 2,000-entry byte-level BPE tokenizer."""
    folder = tmp_path_factory.mktemp("tiny-base")
    texts = [i.prompt for i in ITEMS[:400]] + [template(i) for i in ITEMS[:400]]
    raw = Tokenizer(models.BPE(unk_token="<unk>"))
    raw.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    raw.decoder = decoders.ByteLevel()
    raw.train_from_iterator(
        texts,
        trainers.BpeTrainer(
            vocab_size=2000,
            special_tokens=["<unk>", "<eos>"],
            initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        ),
    )
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=raw, unk_token="<unk>", eos_token="<eos>")
    tokenizer.save_pretrained(folder)
    config = LlamaConfig(
        vocab_size=len(tokenizer),
        hidden_size=64,
        intermediate_size=128,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=2,
        max_position_embeddings=2048,
        eos_token_id=tokenizer.eos_token_id,
    )
    LlamaForCausalLM(config).save_pretrained(folder)
    return folder


@pytest.fixture(scope="session")
def tiny_data(tmp_path_factory):
    folder = tmp_path_factory.mktemp("drafts")
    hints = [i for i in ITEMS if i.task == "hint_level_1"]
    for split, chosen in (("train", hints[:6]), ("val", hints[6:9])):
        with (folder / f"drafts-{split}.jsonl").open("w") as file:
            for row in drafts(chosen):
                file.write(json.dumps(row) + "\n")
    return folder


def config(base, data, out, **overrides):
    settings = {
        "base": str(base),
        "data": str(data),
        "out": str(out),
        "max_length": 2048,
        "batch_size": 2,
        "grad_accum": 1,
        "lr": 3e-3,
        "max_steps": 120,
        "warmup": 0.05,
        "eval_every": 40,
        "save_every": 60,
        "device": "cpu",
    }
    return Config(**(settings | overrides))


@pytest.fixture(scope="session")
def trained(tiny_base, tiny_data, tmp_path_factory):
    out = tmp_path_factory.mktemp("run")
    summary = train(config(tiny_base, tiny_data, out), log=lambda _: None)
    return out, summary
