"""Every seed must be a good model answer: it runs, prints the same thing every
time, and the engine finds nothing at all to say about it."""

from pathlib import Path

import pytest

from pymentor import Engine
from pymentor.exercises import Exercise
from pymentor.sandbox import execute
from pymentor_pipeline.corpus import expected_tests, load_seeds

REPO = Path(__file__).resolve().parents[2]
SEEDS = load_seeds(REPO)
ENGINE = Engine(step_limit=200_000)


def test_there_are_enough_seeds_from_every_source():
    kinds = {seed.id.split(":")[0] for seed in SEEDS}
    assert kinds == {"program", "exercise", "lesson"}
    assert len(SEEDS) >= 100
    assert len({seed.id for seed in SEEDS}) == len(SEEDS)


@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: s.id)
def test_seed_is_clean_and_deterministic(seed):
    exercise = Exercise(seed.id, seed.id, "", "", seed.source, expected_tests(seed))
    report = ENGINE.run_exercise(exercise, seed.source)
    assert report.passed
    assert [f.diagnostic.code for f in report.findings] == []
    # Run twice: a seed's output must not depend on chance or the clock.
    for test in exercise.tests:
        if test.output is not None:
            assert (
                execute(seed.source, list(test.inputs)).printed
                == execute(seed.source, list(test.inputs)).printed
            )


@pytest.mark.parametrize("seed", [s for s in SEEDS if not s.tests], ids=lambda s: s.id)
def test_derived_tests_capture_the_output(seed):
    [test] = expected_tests(seed)
    assert test.inputs == seed.inputs and test.output is not None
