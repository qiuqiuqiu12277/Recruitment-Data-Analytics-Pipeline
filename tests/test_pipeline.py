import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from recruitment_pipeline.cli import main
from recruitment_pipeline.demo import generate_synthetic_jobs
from recruitment_pipeline.pipeline import run_pipeline


def test_pipeline_writes_typed_data_summary_and_charts(tmp_path):
    source = tmp_path / "jobs.csv"
    generate_synthetic_jobs(rows=16, seed=7).to_csv(source, index=False)

    result = run_pipeline(source, tmp_path / "report", top_n=5)

    assert result.records == 16
    assert result.processed_csv.is_file()
    assert result.summary_json.is_file()
    assert len(result.chart_paths) == 3
    assert all(path.is_file() and path.stat().st_size > 0 for path in result.chart_paths)

    processed = pd.read_csv(result.processed_csv)
    assert {
        "experience_min_years",
        "experience_max_years",
        "experience_level",
        "skills",
        "ctr",
    }.issubset(processed.columns)
    assert isinstance(json.loads(processed.loc[0, "skills"]), list)

    summary = json.loads(result.summary_json.read_text(encoding="utf-8"))
    assert summary["records"] == 16
    assert summary["data_quality"]["input_records"] == 16
    assert summary["top_skills"]


def test_module_cli_demo_runs_end_to_end(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root / "src")
    environment["MPLBACKEND"] = "Agg"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "recruitment_pipeline",
            "demo",
            "--output-dir",
            str(tmp_path / "cli-demo"),
            "--rows",
            "9",
            "--seed",
            "11",
            "--no-charts",
        ],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Processed 9 records" in completed.stdout
    assert (tmp_path / "cli-demo" / "synthetic_jobs.csv").is_file()
    assert (tmp_path / "cli-demo" / "processed_jobs.csv").is_file()
    assert (tmp_path / "cli-demo" / "summary.json").is_file()


def test_cli_reports_missing_input_without_a_traceback(tmp_path, capsys):
    result = main(
        [
            "run",
            "--input",
            str(tmp_path / "missing.csv"),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    captured = capsys.readouterr()
    assert result == 2
    assert "input file does not exist" in captured.err
    assert "Traceback" not in captured.err
