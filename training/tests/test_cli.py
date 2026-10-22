"""The command line trains a model and scores it, writing results like the pipeline's."""

import json
import shutil

from conftest import REPO

from pymentor_training import __main__ as cli


def test_train_then_evaluate_from_the_command_line(tiny_base, tiny_data, tmp_path, monkeypatch):
    out = tmp_path / "run"
    paths = ["--base", str(tiny_base), "--data", str(tiny_data), "--out", str(out)]
    options = "--max-steps 3 --batch-size 2 --grad-accum 1 --max-length 2048 --device cpu"
    cli.main(["train", *paths, *options.split(), "--optimizer", "adafactor"])
    assert json.loads((out / "config.json").read_text())["optimizer"] == "adafactor"
    assert json.loads((out / "summary.json").read_text())["steps"] == 3

    benchmarks = tmp_path / "benchmark"
    shutil.copytree(REPO / "benchmark" / "v0", benchmarks / "v0")
    monkeypatch.setattr(cli, "BENCHMARKS", benchmarks)
    cli.main(["evaluate", "--model", str(out / "best"), "--name", "tiny", "--limit", "5"])
    report = json.loads((benchmarks / "results" / "v0" / "tiny.json").read_text())
    assert report["items"] == 5 and report["model"] == "tiny" and report["parameters"] > 0
    assert (benchmarks / "results" / "v0" / "tiny-hand-scoring.csv").exists()
