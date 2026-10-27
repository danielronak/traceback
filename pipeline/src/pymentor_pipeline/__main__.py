"""``python -m pymentor_pipeline``: the data pipeline's commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import benchmark, draft, evaluate, review, teachers
from .generate import DEFAULT_PER_KIND, DEFAULT_VARIANTS, generate, read_jsonl

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

    dr = commands.add_parser("draft", help="have a local teacher model write training targets")
    dr.add_argument("--url", default=teachers.DEFAULT_URL, help="the local model server")
    dr.add_argument("--model", default="local", help="the teacher's name, as the server knows it")
    dr.add_argument("--data", type=Path, default=REPO / "data" / "generated" / "v1")
    dr.add_argument("--split", default="train")
    dr.add_argument("--limit", type=int, default=None)

    im = commands.add_parser("import", help="judge teacher outputs made offline (JSONL)")
    im.add_argument("outputs", type=Path, help="lines of {case, task, output}")
    im.add_argument("--name", required=True, help="the teacher model that wrote them")
    im.add_argument("--data", type=Path, default=REPO / "data" / "generated" / "v1")
    im.add_argument("--split", default="train")

    rv = commands.add_parser("review", help="spot-check drafted targets by hand")
    rv.add_argument("--data", type=Path, default=REPO / "data" / "generated" / "v1")
    rv.add_argument("--split", default="train")
    rv.add_argument("--sample", type=int, default=50)
    rv.add_argument("--summary", action="store_true", help="only print the results so far")

    rp = commands.add_parser("report", help="a drafting checkpoint: counts, reasons, examples")
    rp.add_argument("--data", type=Path, default=REPO / "data" / "generated" / "v1")
    rp.add_argument("--split", default="train")

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
    elif args.command == "draft":
        teacher = teachers.local_teacher(args.url, model=args.model)
        draft.draft(args.data, args.split, teacher, name=args.model, limit=args.limit)
    elif args.command == "import":
        rows = read_jsonl(args.outputs)
        triples = ((r["case"], r["task"], r.get("output")) for r in rows)
        tally = draft.accept_outputs(args.data, args.split, triples, name=args.name)
        print(f"{args.split}: {dict(tally)}")
    elif args.command == "report":
        review.report(args.data, args.split)
    elif args.command == "review":
        if not args.summary:
            print(dict(review.review(args.data, args.split, sample=args.sample)))
        print(json.dumps(review.summary(args.data, args.split), indent=2))
    return 0


def _evaluate(args: argparse.Namespace) -> None:
    todo = evaluate.items(benchmark.load(BENCHMARKS / args.version))
    if args.outputs:
        outputs = evaluate.read_outputs(args.outputs)
        name = args.name or args.outputs.stem
    else:
        outputs = evaluate.run_model(evaluate.load_model(args.model), todo)
        name = args.name or args.model.replace(":", "-").replace(".", "-")
    report, rows = evaluate.save_results(todo, outputs, name, args.version, BENCHMARKS)
    overall = report["overall"]
    print(
        f"{name} on {args.version}: {report['items']} items, grounded {overall['grounded']:.1%}, "
        f"{overall['mean_words']} words on average, fix {overall['fix_ok']}, "
        f"{rows} rows to score by hand -> benchmark/results/{args.version}/"
    )


if __name__ == "__main__":
    raise SystemExit(main())
