"""The generator: verified cases, split by seed group, deterministic files."""

import json
import time
from pathlib import Path

import pytest

from pymentor import grounding, prompt
from pymentor_pipeline.corpus import Seed, load_seeds
from pymentor_pipeline.generate import (
    _TIMED_OUT,
    Job,
    analyse,
    generate,
    group_of,
    make_jobs,
    read_jsonl,
    run_jobs,
    split_of,
)
from pymentor_pipeline.records import finding_from_record

REPO = Path(__file__).resolve().parents[2]
SOME_SEEDS = load_seeds(REPO)[::5]


def test_groups_keep_a_seeds_relatives_together():
    assert group_of("lesson:loops#3") == group_of("lesson:loops#1~2") == "lesson:loops"
    assert group_of("program:010-sum-to-n~1") == "program:010-sum-to-n"
    for seed_id in ("lesson:loops#1", "lesson:loops#4~2"):
        assert split_of(seed_id) == split_of("lesson:loops")


def test_splits_are_roughly_80_10_10():
    splits = [split_of(f"program:{n}") for n in range(2000)]
    assert 0.75 < splits.count("train") / 2000 < 0.85
    assert splits.count("val") > 100 and splits.count("test") > 100


def test_analyse_returns_the_finding_the_app_would_show():
    seed = Seed("program:t", "total = 3\nif total > 2:\n    print(total)\n")
    job = next(j for j in make_jobs([seed], per_kind=1) if j.kind == "drop_colon")
    finding = finding_from_record(analyse(job))
    assert finding.card.id == "missing-colon"
    assert finding.fix is not None
    # The record keeps the features grounding needs, and survives JSON.
    again = finding_from_record(json.loads(json.dumps(analyse(job))))
    assert again == finding
    assert grounding.allowed_lines(again) == grounding.allowed_lines(finding)


def _slow(job):
    if job.kind == "hang":
        time.sleep(60)
    return job.index


def test_a_job_that_hangs_is_killed_and_the_rest_still_finish():
    jobs = [Job(i, "s", "hang" if i == 1 else "ok", 1, "", ()) for i in range(4)]
    results = {job.index: result for job, result in run_jobs(jobs, _slow, timeout=1)}
    assert results[1] is _TIMED_OUT
    assert {i: r for i, r in results.items() if i != 1} == {0: 0, 2: 2, 3: 3}


@pytest.fixture(scope="module")
def small_dataset(tmp_path_factory):
    out = tmp_path_factory.mktemp("data")
    manifest = generate(
        REPO, out, per_kind=2, variant_count=1, workers=2, log=lambda _: None, only=SOME_SEEDS
    )
    return out, manifest


def test_every_case_has_a_card_and_lands_in_its_seeds_split(small_dataset):
    out, manifest = small_dataset
    assert sum(manifest["cases"].values()) > 300
    assert manifest["variants"] > 0
    groups = {}
    for split in ("train", "val", "test"):
        for case in read_jsonl(out / f"cases-{split}.jsonl"):
            assert case["finding"]["card"] is not None
            assert split_of(case["seed"]) == split
            assert groups.setdefault(case["group"], split) == split


def test_examples_are_built_by_the_shared_prompt_format(small_dataset):
    out, _ = small_dataset
    cases = {c["id"]: c for c in read_jsonl(out / "cases-train.jsonl")}
    examples = read_jsonl(out / "examples-train.jsonl")
    for example in examples[:50]:
        case = cases[example["case"]]
        finding = finding_from_record(case["finding"])
        assert example["prompt"] == prompt.build(finding, case["source"], example["task"])
    assert {e["task"] for e in examples} >= set(prompt.tasks_for(finding))


def test_the_same_inputs_give_the_same_files(small_dataset, tmp_path):
    _, manifest = small_dataset
    again = generate(
        REPO, tmp_path, per_kind=2, variant_count=1, workers=3, log=lambda _: None, only=SOME_SEEDS
    )
    assert again["files"] == manifest["files"]
