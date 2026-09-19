"""Command-line interface for the recruitment analytics pipeline."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .demo import write_synthetic_jobs
from .pipeline import PipelineError, PipelineResult, run_pipeline
from .review import approve_review_queue, create_review_package, export_approved_jobs


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
    parser.add_argument("--version", action="version", version="%(prog)s 0.3.0")
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

    review = commands.add_parser("review", help="build a row-conserving quality review queue")
    review.add_argument("--input", type=Path, required=True, help="processed_jobs.csv")
    review.add_argument("--output-dir", type=Path, default=Path("outputs/review"))

    approve = commands.add_parser(
        "approve", help="apply explicit human decisions and create an approval manifest"
    )
    approve.add_argument("--review-queue", type=Path, required=True)
    approve.add_argument("--decisions", type=Path, required=True)
    approve.add_argument("--output-dir", type=Path, default=Path("outputs/approved"))

    export = commands.add_parser(
        "export", help="verify an approval manifest and export approved records"
    )
    export.add_argument("--approved", type=Path, required=True)
    export.add_argument("--manifest", type=Path, required=True)
    export.add_argument("--output", type=Path, default=Path("outputs/exported_jobs.csv"))

    workflow_demo = commands.add_parser(
        "workflow-demo",
        help="run the complete gated workflow with synthetic data and demo decisions",
    )
    workflow_demo.add_argument("--output-dir", type=Path, default=Path("outputs/workflow-demo"))
    workflow_demo.add_argument("--rows", type=_positive_integer, default=100)
    workflow_demo.add_argument("--seed", type=int, default=42)
    workflow_demo.add_argument("--top-n", type=_positive_integer, default=10)
    workflow_demo.add_argument("--no-charts", action="store_true", help="skip PNG chart generation")
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

        if args.command == "review":
            result = create_review_package(args.input, args.output_dir)
            print(
                f"Review queue: {result.records} records; "
                f"{result.decisions_required} require decisions."
            )
            print(f"Queue: {result.review_queue_csv.resolve()}")
            print(f"Decisions template: {result.decisions_template_csv.resolve()}")
            return 0

        if args.command == "approve":
            result = approve_review_queue(
                args.review_queue,
                args.decisions,
                args.output_dir,
            )
            print(
                f"Approval complete: {result.approved_records} approved, "
                f"{result.rejected_records} rejected."
            )
            print(f"Manifest: {result.manifest_json.resolve()}")
            return 0

        if args.command == "export":
            result = export_approved_jobs(args.approved, args.manifest, args.output)
            print(f"Exported {result.records} approved records: {result.export_csv.resolve()}")
            print(f"Receipt: {result.receipt_json.resolve()}")
            return 0

        if args.command == "workflow-demo":
            args.output_dir.mkdir(parents=True, exist_ok=True)
            demo_csv = write_synthetic_jobs(
                args.output_dir / "synthetic_jobs.csv", rows=args.rows, seed=args.seed
            )
            analytics = run_pipeline(
                demo_csv,
                args.output_dir / "analytics",
                top_n=args.top_n,
                include_charts=not args.no_charts,
            )
            review = create_review_package(
                analytics.processed_csv,
                args.output_dir / "review",
            )
            decisions = pd.read_csv(review.decisions_template_csv, encoding="utf-8-sig")
            decisions["decision"] = decisions["quality_status"].map(
                {"warning": "approve", "critical": "reject"}
            )
            decisions["reviewer"] = "synthetic-demo-policy"
            decisions["note"] = "demo only: approve warnings and reject critical records"
            demo_decisions = args.output_dir / "review" / "demo_decisions.csv"
            decisions.to_csv(demo_decisions, index=False)
            approval = approve_review_queue(
                review.review_queue_csv,
                demo_decisions,
                args.output_dir / "approved",
            )
            exported = export_approved_jobs(
                approval.approved_csv,
                approval.manifest_json,
                args.output_dir / "delivery" / "jobs.csv",
            )
            print(
                f"Workflow demo complete: {analytics.records} reviewed, "
                f"{approval.approved_records} approved, {approval.rejected_records} rejected, "
                f"{exported.records} exported."
            )
            print(f"Manifest: {approval.manifest_json.resolve()}")
            return 0
    except (OSError, PipelineError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
