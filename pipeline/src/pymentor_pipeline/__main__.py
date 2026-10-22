"""``python -m pymentor_pipeline``: the data pipeline's commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import benchmark, evaluate
from .generate import DEFAULT_PER_KIND, DEFAULT_VARIANTS, generate

REPO = Path(__file__).resolve().parents[3]
BENCHMARKS = REPO / "benchmark"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pymentor-pipeline")
    commands = parser.add_subparsers(dest="command", required=True)

    gen = commands.add_parser("generate", help="mutate the seeds and write the dataset")
    gen.add_argument("--out", type=Path, default=REPO / "data" / "generated" / "v1")
    gen.add_argument("--per-kind", type=int, default=DEFAULT_PER_KIND)
    gen.add_argument("--variants", type=int, default=DEFAULT_VARIANTS)
    gen.add_argument("--workers", type=int, default=None)

    bench = commands.add_parser("benchmark", help="build and freeze a benchmark version")
    bench.add_argument("--version", default=benchmark.VERSION)

    ev = commands.add_parser("evaluate", help="score a model on a benchmark version")
    ev.add_argument("--model", default="template", help="'template' or module:function")
    ev.add_argument("--outputs", type=Path, help="score saved outputs (JSONL) instead")
    ev.add_argument("--version", default=benchmark.VERSION)
    ev.add_argument("--name", help="results name (default: the model's)")

    args = parser.parse_args(argv)
    if args.command == "generate":
        generate(
            REPO,
            args.out,
            per_kind=args.per_kind,
            variant_count=args.variants,
            workers=args.workers,
        )
    elif args.command == "benchmark":
        cases = benchmark.build(REPO)
        digest = benchmark.write(cases, BENCHMARKS / args.version)
        print(f"{len(cases)} cases frozen in benchmark/{args.version} (sha256 {digest[:12]})")
    elif args.command == "evaluate":
        _evaluate(args)
    return 0


def _evaluate(args: argparse.Namespace) -> None:
    todo = evaluate.items(benchmark.load(BENCHMARKS / args.version))
    if args.outputs:
        outputs = evaluate.read_outputs(args.outputs)
        name = args.name or args.outputs.stem
    else:
        outputs = evaluate.run_model(evaluate.load_model(args.model), todo)
        name = args.name or args.model.replace(":", "-").replace(".", "-")
    report = evaluate.score(todo, outputs) | {"model": name, "benchmark": args.version}
    folder = BENCHMARKS / "results" / args.version
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (folder / f"{name}-outputs.jsonl").open("w", encoding="utf-8") as file:
        for output in outputs:
            file.write(json.dumps({**output, "ms": round(output.get("ms") or 0, 3)}) + "\n")
    rows = evaluate.hand_sheet(todo, outputs, folder / f"{name}-hand-scoring.csv")
    overall = report["overall"]
    print(
        f"{name} on {args.version}: {report['items']} items, grounded {overall['grounded']:.1%}, "
        f"{overall['mean_words']} words on average, fix {overall['fix_ok']}, "
        f"{rows} rows to score by hand -> benchmark/results/{args.version}/"
    )


if __name__ == "__main__":
    raise SystemExit(main())
