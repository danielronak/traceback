"""``python -m pymentor_training``: train and evaluate the tutor model."""

from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

from pymentor_pipeline import benchmark, evaluate

from .sft import Config, train

REPO = Path(__file__).resolve().parents[3]
BENCHMARKS = REPO / "benchmark"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pymentor-training")
    commands = parser.add_subparsers(dest="command", required=True)

    tr = commands.add_parser("train", help="fine-tune a base model on drafted targets")
    defaults = Config(base="", data="", out="")
    for f in dataclasses.fields(Config):
        if f.name == "notes":
            continue
        flag = "--" + f.name.replace("_", "-")
        if f.name in ("base", "data", "out"):
            tr.add_argument(flag, required=True)
        elif f.type == "bool":
            tr.add_argument(flag, action="store_true")
        else:
            kind = {"int": int, "float": float, "int | None": int}.get(str(f.type), str)
            tr.add_argument(flag, type=kind, default=getattr(defaults, f.name))
    tr.add_argument("--resume", action="store_true", help="continue from out/last")

    ev = commands.add_parser("evaluate", help="score a trained model on a benchmark version")
    ev.add_argument("--model", required=True, type=Path, help="a trained model folder")
    ev.add_argument("--name", required=True, help="results name, e.g. smollm2-360m-sft")
    ev.add_argument("--version", default=benchmark.VERSION)
    ev.add_argument("--device", default="auto")
    ev.add_argument("--limit", type=int, default=None, help="only the first N items (a quick look)")
    ev.add_argument("--onnx", default=None, help="score an exported file, e.g. model_q4.onnx")

    ex = commands.add_parser("export", help="export a trained model to ONNX and int4 ONNX")
    ex.add_argument("--model", required=True, type=Path, help="a trained model folder")
    ex.add_argument("--out", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "train":
        options = {
            f.name: getattr(args, f.name) for f in dataclasses.fields(Config) if f.name != "notes"
        }
        print(train(Config(**options), resume=args.resume))
    elif args.command == "evaluate":
        _evaluate(args)
    elif args.command == "export":
        from .export import export

        for name, size in export(args.model, args.out).items():
            print(f"{name}: {size / 1e6:.1f} MB")
    return 0


def _evaluate(args: argparse.Namespace) -> None:
    from .infer import Tutor

    tutor = Tutor(args.model, device=args.device, onnx_file=args.onnx)
    todo = evaluate.items(benchmark.load(BENCHMARKS / args.version))[: args.limit]
    outputs = evaluate.run_model(tutor, todo)
    extra = {
        "parameters": tutor.parameters,
        "device": str(tutor.device),
        "path": str(args.model),
        "onnx_file": args.onnx,
    }
    report, rows = evaluate.save_results(todo, outputs, args.name, args.version, BENCHMARKS, extra)
    overall = report["overall"]
    print(
        f"{args.name} on {args.version}: {report['items']} items, "
        f"grounded {overall['grounded']:.1%}, "
        f"fix {overall['fix_ok']}, {overall['mean_words']} words, p50 {overall['ms_p50']} ms, "
        f"{rows} rows to score by hand -> benchmark/results/{args.version}/"
    )


if __name__ == "__main__":
    raise SystemExit(main())
