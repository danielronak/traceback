"""The dataset generator: seeds in, verified model inputs out.

For every seed program it makes mutations, has the engine analyse each one
exactly as the app would, and keeps those whose first finding has a rule card.
Each kept *case* becomes one *example* per task (``prompt.tasks_for``), with
the prompt built by ``pymentor.prompt`` (D10). The targets are written later,
by the teacher (``draft``) or the card template (``baseline``).

Every analysis runs in a worker process with a hard timeout (D24): a mutation
can turn a loop infinite or ask for ``10 ** 10 ** 10``, and one bad program
must never stall the whole run.

Cases are split into train, val and test by seed *group* (D16): all mutations
of one program, and every snippet of one lesson, land in the same split.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import time
import warnings
from collections import Counter, deque
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from multiprocessing.connection import Connection, wait
from pathlib import Path
from typing import Any

from pymentor import Engine, prompt
from pymentor.exercises import Exercise, ExerciseTest, parse_tests

from .augment import variants
from .corpus import Seed, expected_tests, load_seeds
from .mutate import mutate
from .records import finding_from_record, finding_to_record

SPLITS = (("train", 80), ("val", 90), ("test", 100))  # cumulative percentages
DEFAULT_PER_KIND = 12
DEFAULT_VARIANTS = 2  # renamed copies of each seed (augment.py)
JOB_TIMEOUT = 20.0  # seconds; the sandbox's own limits normally stop a program long before
MEMORY_LIMIT = 1 << 30  # bytes per worker
MAX_DEATHS_IN_A_ROW = 20  # then something is wrong with the workers, not the jobs


@dataclass(frozen=True)
class Job:
    index: int
    seed: str
    kind: str
    line: int  # where the mutation was made
    source: str
    tests: tuple[dict[str, Any], ...]


def group_of(seed_id: str) -> str:
    """The unit that is never split: a program with its variants, an exercise,
    or a whole lesson."""
    return seed_id.split("~", 1)[0].split("#", 1)[0]


def split_of(seed_id: str) -> str:
    bucket = int(hashlib.sha256(group_of(seed_id).encode()).hexdigest(), 16) % 100
    return next(name for name, upto in SPLITS if bucket < upto)


def case_id(seed_id: str, source: str) -> str:
    return hashlib.sha256(f"{seed_id}\n{source}".encode()).hexdigest()[:16]


def make_jobs(seeds: Iterable[Seed], per_kind: int) -> list[Job]:
    jobs: list[Job] = []
    for seed in seeds:
        tests = tuple(test_to_dict(t) for t in expected_tests(seed))
        for mutation in mutate(seed.source, per_kind=per_kind, seed=seed.id):
            jobs.append(
                Job(len(jobs), seed.id, mutation.kind, mutation.line, mutation.source, tests)
            )
    return jobs


_ENGINE: Engine | None = None


def analyse(job: Job) -> dict[str, Any] | None:
    """The first finding the app would show for this mutation, as a record."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = Engine()
    exercise = Exercise(job.seed, job.seed, "", "", "", parse_tests(list(job.tests), job.seed))
    findings = _ENGINE.run_exercise(exercise, job.source).findings
    return finding_to_record(findings[0]) if findings else None


def generate(
    repo: Path,
    out: Path,
    *,
    per_kind: int = DEFAULT_PER_KIND,
    variant_count: int = DEFAULT_VARIANTS,
    workers: int | None = None,
    log: Callable[[str], object] = print,
    only: Iterable[Seed] | None = None,
) -> dict[str, Any]:
    """Build the dataset in ``out``; returns the manifest it also writes there.
    ``only`` limits it to some seeds (for tests)."""
    started = time.monotonic()
    originals = list(only) if only is not None else load_seeds(repo)
    seeds = [s for seed in originals for s in (seed, *variants(seed, variant_count))]
    jobs = make_jobs(seeds, per_kind)
    log(f"{len(originals)} seeds and {len(seeds) - len(originals)} variants, {len(jobs)} mutations")

    results: dict[int, dict[str, Any] | None] = {}
    timed_out = 0
    for done, (job, result) in enumerate(run_jobs(jobs, analyse, workers=workers), start=1):
        if result is TIMED_OUT:
            timed_out += 1
            result = None
        results[job.index] = result
        if done % 2000 == 0:
            log(f"  analysed {done}/{len(jobs)}")

    tally: Counter[str] = Counter()
    seen: set[str] = set()
    cases: dict[str, list[dict[str, Any]]] = {name: [] for name, _ in SPLITS}
    examples: dict[str, list[dict[str, Any]]] = {name: [] for name, _ in SPLITS}
    for job in jobs:  # job order, so the output never depends on which worker finished first
        record = results[job.index]
        if record is None:
            tally["no finding"] += 1
            continue
        finding = finding_from_record(record)
        if finding.card is None:
            tally["no card"] += 1
            continue
        # Two mutations that give the model the same input are one example.
        key = prompt.build(finding, job.source, "explain")
        if key in seen:
            tally["duplicate"] += 1
            continue
        seen.add(key)
        split = split_of(job.seed)
        cid = case_id(job.seed, job.source)
        cases[split].append(
            {
                "id": cid,
                "seed": job.seed,
                "group": group_of(job.seed),
                "kind": job.kind,
                "mutated_line": job.line,
                "source": job.source,
                "tests": list(job.tests),
                "finding": record,
            }
        )
        for task in prompt.tasks_for(finding):
            examples[split].append(
                {
                    "case": cid,
                    "task": task,
                    "card": finding.card.id,
                    "prompt": prompt.build(finding, job.source, task),
                }
            )

    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, _ in SPLITS:
        files[f"cases-{name}.jsonl"] = _write_jsonl(out / f"cases-{name}.jsonl", cases[name])
        files[f"examples-{name}.jsonl"] = _write_jsonl(
            out / f"examples-{name}.jsonl", examples[name]
        )
    every_case = [case for name, _ in SPLITS for case in cases[name]]
    manifest = {
        "prompt_version": prompt.PROMPT_VERSION,
        "per_kind": per_kind,
        "variants_per_seed": variant_count,
        "seeds": len(originals),
        "variants": len(seeds) - len(originals),
        "mutations": len(jobs),
        "dropped": dict(sorted(tally.items())) | {"timed out": timed_out},
        "cases": {name: len(cases[name]) for name, _ in SPLITS},
        "examples": {name: len(examples[name]) for name, _ in SPLITS},
        "groups": {name: sorted({case["group"] for case in cases[name]}) for name, _ in SPLITS},
        "cards": dict(Counter(c["finding"]["card"]["id"] for c in every_case).most_common()),
        "kinds": dict(Counter(c["kind"] for c in every_case).most_common()),
        "files": files,
        "seconds": round(time.monotonic() - started, 1),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    total = sum(manifest["examples"].values())
    log(f"{len(every_case)} cases, {total} examples in {manifest['seconds']}s -> {out}")
    return manifest


# --- Worker processes ------------------------------------------------------

TIMED_OUT = object()


def run_jobs(
    jobs: Iterable[Job],
    fn: Callable[[Job], Any],
    *,
    workers: int | None = None,
    timeout: float = JOB_TIMEOUT,
) -> Iterator[tuple[Job, Any]]:
    """Run ``fn`` on each job in a pool of processes, killing any that overrun.

    Yields ``(job, result)`` as jobs finish, in no particular order. A job that
    times out or kills its worker yields ``TIMED_OUT`` and gets a fresh worker.
    ``fn`` must be a module-level function, since workers are spawned.
    """
    context = multiprocessing.get_context("spawn")
    count = workers or max(1, (multiprocessing.cpu_count() or 2) - 1)
    pending = deque(jobs)
    idle = [_Worker(context, fn) for _ in range(min(count, len(pending)) or 1)]
    busy: dict[Connection, _Worker] = {}
    deaths = 0
    try:
        while pending or busy:
            while pending and idle:
                worker = idle.pop()
                worker.start(pending.popleft(), timeout)
                busy[worker.conn] = worker
            soonest = min(w.deadline for w in busy.values())
            for conn in wait(list(busy), timeout=max(0.0, soonest - time.monotonic())):
                worker = busy.pop(conn)
                job = worker.job
                try:
                    result = conn.recv()
                except (EOFError, OSError):  # the worker died mid-job
                    result = TIMED_OUT
                    worker.stop()
                    deaths += 1
                    if deaths > MAX_DEATHS_IN_A_ROW:
                        raise RuntimeError(
                            "workers keep dying; run from a file or module, not stdin"
                        ) from None
                    worker = _Worker(context, fn)
                else:
                    deaths = 0
                yield job, result
                idle.append(worker)
            now = time.monotonic()
            for conn, worker in list(busy.items()):
                if worker.deadline <= now:
                    del busy[conn]
                    job = worker.job
                    worker.stop()
                    idle.append(_Worker(context, fn))
                    yield job, TIMED_OUT
    finally:
        for worker in [*idle, *busy.values()]:
            worker.stop()


class _Worker:
    def __init__(self, context: Any, fn: Callable[[Job], Any]) -> None:
        self.conn, child = context.Pipe()
        self.process = context.Process(target=_serve, args=(child, fn), daemon=True)
        self.process.start()
        child.close()
        self.job: Job | None = None
        self.deadline = 0.0

    def start(self, job: Job, timeout: float) -> None:
        self.job, self.deadline = job, time.monotonic() + timeout
        self.conn.send(job)

    def stop(self) -> None:
        if self.process.is_alive():
            self.process.kill()
        self.process.join()
        self.conn.close()


def _serve(conn: Connection, fn: Callable[[Job], Any]) -> None:
    # Compiling broken code raises SyntaxWarnings; in bulk they're only noise.
    warnings.simplefilter("ignore", SyntaxWarning)
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (ImportError, ValueError, OSError):
        pass  # not on this platform; the timeout still applies
    while True:
        try:
            job = conn.recv()
        except EOFError:
            return
        try:
            result = fn(job)
        except Exception:  # an engine bug on one mutation shouldn't end the run
            result = None
        conn.send(result)


# --- Files -----------------------------------------------------------------


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")
    return {"rows": len(rows), "sha256": hashlib.sha256(text.encode()).hexdigest()}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def test_to_dict(test: ExerciseTest) -> dict[str, Any]:
    """A test as an exercise file writes it, so ``parse_tests`` reads it back."""
    if test.call is not None:
        return {"call": test.call, "expect": test.expect_text, "inputs": list(test.inputs)}
    return {"inputs": list(test.inputs), "output": test.output}
