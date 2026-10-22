"""``python -m pymentor_pipeline``: the data pipeline's commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from .generate import DEFAULT_PER_KIND, DEFAULT_VARIANTS, generate

REPO = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pymentor-pipeline")
    commands = parser.add_subparsers(dest="command", required=True)

    gen = commands.add_parser("generate", help="mutate the seeds and write the dataset")
    gen.add_argument("--out", type=Path, default=REPO / "data" / "generated" / "v1")
    gen.add_argument("--per-kind", type=int, default=DEFAULT_PER_KIND)
    gen.add_argument("--variants", type=int, default=DEFAULT_VARIANTS)
    gen.add_argument("--workers", type=int, default=None)

    args = parser.parse_args(argv)
    if args.command == "generate":
        generate(
            REPO,
            args.out,
            per_kind=args.per_kind,
            variant_count=args.variants,
            workers=args.workers,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
