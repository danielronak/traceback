"""Export gives transformers.js's layout, and the ONNX model answers like the original."""

import json

from pymentor_training.export import export
from pymentor_training.infer import Tutor


def test_export_writes_full_and_int4_models_that_answer(trained, tiny_data, tmp_path):
    out, _ = trained
    sizes = export(out / "best", tmp_path / "web")
    assert {"onnx/model.onnx", "onnx/model_q4.onnx"} <= set(sizes)
    for name in ("config.json", "tokenizer.json", "export.json"):
        assert (tmp_path / "web" / name).exists(), name

    prompt = json.loads((tiny_data / "drafts-train.jsonl").open().readline())["prompt"]
    original = Tutor(out / "best", device="cpu", max_new_tokens=30).generate(prompt)
    full = Tutor(tmp_path / "web", onnx_file="model.onnx", max_new_tokens=30)
    assert full.generate(prompt) == original  # same weights, same greedy answer
    q4 = Tutor(tmp_path / "web", onnx_file="model_q4.onnx", max_new_tokens=30)
    assert isinstance(q4.generate(prompt), str)
    assert q4.parameters is None
