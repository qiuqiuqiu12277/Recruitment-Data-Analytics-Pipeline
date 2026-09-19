"""Command-line interface for the recruitment analytics pipeline."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .demo import write_synthetic_jobs
from .pipeline import PipelineError, PipelineResult, run_pipeline


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recruitment-pipeline",
        description="Validate, enrich, and analyse recruitment CSV data.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.2.0")
    commands = parser.add_subparsers(dest="command")

    run = commands.add_parser("run", help="run the pipeline on a CSV file")
    run.add_argument("--input", type=Path, required=True, help="source recruitment CSV")
    run.add_argument("--output-dir", type=Path, default=Path("outputs"))
    run.add_argument("--skills-config", type=Path, help="optional skill-alias JSON mapping")
    run.add_argument("--top-n", type=_positive_integer, default=10)
    run.add_argument("--no-charts", action="store_true", help="skip PNG chart generation")

    generate = commands.add_parser(
        "generate-demo", help="write deterministic, privacy-safe synthetic data"
    )
    generate.add_argument("--output", type=Path, default=Path("data/demo_jobs.csv"))
    generate.add_argument("--rows", type=_positive_integer, default=100)
    generate.add_argument("--seed", type=int, default=42)

    demo = commands.add_parser("demo", help="generate synthetic data and run the pipeline")
    demo.add_argument("--output-dir", type=Path, default=Path("outputs/demo"))
    demo.add_argument("--rows", type=_positive_integer, default=100)
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--top-n", type=_positive_integer, default=10)
    demo.add_argument("--no-charts", action="store_true", help="skip PNG chart generation")
    return parser


def _print_result(result: PipelineResult) -> None:
    print(f"Processed {result.records} records.")
    print(f"Data: {result.processed_csv.resolve()}")
    print(f"Summary: {result.summary_json.resolve()}")
    if result.chart_paths:
        print(f"Charts: {result.chart_paths[0].parent.resolve()}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "generate-demo":
            path = write_synthetic_jobs(args.output, rows=args.rows, seed=args.seed)
            print(f"Generated {args.rows} synthetic records: {path.resolve()}")
            return 0

        if args.command == "run":
            result = run_pipeline(
                args.input,
                args.output_dir,
                skills_config=args.skills_config,
                top_n=args.top_n,
                include_charts=not args.no_charts,
            )
            _print_result(result)
            return 0

        if args.command == "demo":
            args.output_dir.mkdir(parents=True, exist_ok=True)
            demo_csv = write_synthetic_jobs(
                args.output_dir / "synthetic_jobs.csv", rows=args.rows, seed=args.seed
            )
            result = run_pipeline(
                demo_csv,
                args.output_dir,
                top_n=args.top_n,
                include_charts=not args.no_charts,
            )
            _print_result(result)
            return 0
    except (OSError, PipelineError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
