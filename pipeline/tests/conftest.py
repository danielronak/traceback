"""A small generated dataset, built once for every test that needs one."""

from pathlib import Path

import pytest

from pymentor_pipeline.corpus import load_seeds
from pymentor_pipeline.generate import generate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def small_dataset(tmp_path_factory):
    """(folder, manifest) for every fifth seed, two mutations per kind, one variant each."""
    out = tmp_path_factory.mktemp("data")
    manifest = generate(
        REPO,
        out,
        per_kind=2,
        variant_count=1,
        workers=2,
        log=lambda _: None,
        only=load_seeds(REPO)[::5],
    )
    return out, manifest
