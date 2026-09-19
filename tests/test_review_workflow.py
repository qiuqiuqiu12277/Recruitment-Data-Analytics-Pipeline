import json

import pandas as pd
import pytest

from recruitment_pipeline.cli import main
from recruitment_pipeline.pipeline import run_pipeline
from recruitment_pipeline.review import (
    WorkflowError,
    approve_review_queue,
    create_review_package,
    export_approved_jobs,
)


def _processed_fixture(tmp_path):
    source = tmp_path / "jobs.csv"
    frame = pd.DataFrame(
        [
            {
                "job_id": "JOB-1",
                "job_title": "Data Analyst",
                "job_description": (
                    "At least 3 years of experience using Python and SQL for analytics."
                ),
                "location": "Shanghai",
                "views": 100,
                "clicks": 12,
                "date": "2026-01-01",
            },
            {
                "job_id": "JOB-2",
                "job_title": "Analyst",
                "job_description": "Python",
                "location": "",
                "views": 0,
                "clicks": 0,
                "date": "2026-01-02",
            },
            {
                "job_id": "JOB-3",
                "job_title": "Assistant",
                "job_description": "",
                "location": "Beijing",
                "views": 50,
                "clicks": 3,
                "date": "2026-01-03",
            },
        ]
    )
    frame.to_csv(source, index=False)
    return run_pipeline(source, tmp_path / "analytics", include_charts=False).processed_csv


def test_review_approval_and_manifest_verified_export(tmp_path):
    processed = _processed_fixture(tmp_path)
    review = create_review_package(processed, tmp_path / "review")
    queue = pd.read_csv(review.review_queue_csv)
    summary = json.loads(review.summary_json.read_text(encoding="utf-8"))

    assert review.records == 3
    assert set(queue["quality_status"]) == {"clean", "warning", "critical"}
    assert summary["invariants"]["row_count_conserved"] is True
    assert sum(summary["records"][name] for name in ("clean", "warning", "critical")) == 3

    decisions = pd.read_csv(review.decisions_template_csv)
    decisions["decision"] = decisions["quality_status"].map(
        {"warning": "approve", "critical": "reject"}
    )
    decisions["reviewer"] = "portfolio-reviewer"
    decisions.to_csv(review.decisions_template_csv, index=False)

    approval = approve_review_queue(
        review.review_queue_csv,
        review.decisions_template_csv,
        tmp_path / "approved",
    )
    manifest = json.loads(approval.manifest_json.read_text(encoding="utf-8"))
    assert approval.approved_records == 2
    assert approval.rejected_records == 1
    assert manifest["invariants"]["row_count_conserved"] is True
    assert manifest["counts"]["unresolved"] == 0

    exported = export_approved_jobs(
        approval.approved_csv,
        approval.manifest_json,
        tmp_path / "delivery" / "jobs.csv",
    )
    assert exported.records == 2
    assert exported.export_csv.is_file()
    assert exported.receipt_json.is_file()

    approval.approved_csv.write_text(
        approval.approved_csv.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(WorkflowError, match="hash does not match"):
        export_approved_jobs(
            approval.approved_csv,
            approval.manifest_json,
            tmp_path / "delivery" / "tampered.csv",
        )


def test_flagged_records_cannot_bypass_decisions(tmp_path):
    processed = _processed_fixture(tmp_path)
    review = create_review_package(processed, tmp_path / "review")
    with pytest.raises(WorkflowError, match="require an explicit decision"):
        approve_review_queue(
            review.review_queue_csv,
            review.decisions_template_csv,
            tmp_path / "approved",
        )


def test_review_cli_writes_queue_and_template(tmp_path, capsys):
    processed = _processed_fixture(tmp_path)
    output = tmp_path / "cli-review"
    assert main(["review", "--input", str(processed), "--output-dir", str(output)]) == 0
    captured = capsys.readouterr()
    assert "require decisions" in captured.out
    assert (output / "review_queue.csv").is_file()
    assert (output / "decisions_template.csv").is_file()


def test_workflow_demo_cli_runs_all_gates(tmp_path, capsys):
    output = tmp_path / "workflow-demo"
    assert (
        main(
            [
                "workflow-demo",
                "--output-dir",
                str(output),
                "--rows",
                "12",
                "--seed",
                "9",
                "--no-charts",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "Workflow demo complete" in captured.out
    assert (output / "approved" / "approval_manifest.json").is_file()
    assert (output / "delivery" / "jobs.csv").is_file()
    assert (output / "delivery" / "jobs.receipt.json").is_file()
