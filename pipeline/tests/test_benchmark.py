"""Benchmark versions stay frozen and held out."""

import hashlib
from pathlib import Path

import pytest

from pymentor import prompt
from pymentor_pipeline import benchmark
from pymentor_pipeline.corpus import load_seeds
from pymentor_pipeline.generate import split_of
from pymentor_pipeline.records import finding_from_record

ROOT = Path(__file__).resolve().parents[2] / "benchmark"
VERSIONS = sorted(p for p in ROOT.iterdir() if (p / "SHA256SUMS").exists())


@pytest.mark.parametrize("folder", VERSIONS, ids=lambda p: p.name)
def test_version_matches_its_checksums(folder):
    for line in (folder / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest, (
            f"{folder.name}/{name} changed. Benchmark versions are frozen: build a new one."
        )


@pytest.mark.parametrize("folder", VERSIONS, ids=lambda p: p.name)
def test_cases_are_held_out_and_complete(folder):
    seeds = {s.source for s in load_seeds(ROOT.parent)}
    cases = benchmark.load(folder)
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        finding = finding_from_record(case["finding"])
        assert finding.card is not None
        assert case["source"] not in seeds  # a broken program, never a seed itself
        if case["origin"] == "mutation":
            assert split_of(case["seed"]) == "test"
        prompt.build(finding, case["source"], "explain")


def test_a_frozen_version_is_never_overwritten(tmp_path):
    benchmark.write([], tmp_path)
    with pytest.raises(FileExistsError):
        benchmark.write([], tmp_path)


def test_sampling_spreads_cases_across_cards():
    cases = [
        {"id": f"{card}-{n}", "finding": {"card": {"id": card}}}
        for card, many in (("common", 50), ("rare", 2))
        for n in range(many)
    ]
    chosen = benchmark._sample_evenly(cases, 6)
    assert sum(c["finding"]["card"]["id"] == "rare" for c in chosen) == 2
