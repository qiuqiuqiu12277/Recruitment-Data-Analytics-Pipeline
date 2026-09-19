import math

import pandas as pd
import pytest

from recruitment_pipeline.analysis import build_summary, calculate_ctr
from recruitment_pipeline.preprocessing import preprocess_jobs
from recruitment_pipeline.schema import SchemaValidationError


def _valid_frame():
    return pd.DataFrame(
        {
            " Job ID ": ["A-1", "A-2"],
            "Job Title": [" Data Analyst ", "ML Engineer"],
            "Job Description": ["  Python   and SQL  ", "机器学习"],
            "Location": ["Shanghai", "Beijing"],
            "Views": [10, 0],
            "Clicks": [2, 0],
            "Date": ["2026-01-01", "2026-01-02"],
        }
    )


def test_preprocessing_normalises_headers_text_and_types():
    result = preprocess_jobs(_valid_frame())
    assert result.columns.tolist() == [
        "job_id",
        "job_title",
        "job_description",
        "location",
        "views",
        "clicks",
        "date",
    ]
    assert result.loc[0, "job_title"] == "Data Analyst"
    assert result.loc[0, "job_description"] == "Python and SQL"
    assert str(result["views"].dtype) == "int64"


def test_schema_reports_multiple_input_problems():
    frame = _valid_frame()
    frame["Clicks"] = frame["Clicks"].astype(object)
    frame.loc[0, "Views"] = -1
    frame.loc[1, "Clicks"] = "not-a-number"
    frame.loc[1, "Date"] = "not-a-date"
    with pytest.raises(SchemaValidationError) as caught:
        preprocess_jobs(frame)
    message = str(caught.value)
    assert "views is negative" in message
    assert "clicks is not numeric" in message
    assert "date is invalid" in message


def test_conflicting_duplicate_ids_are_rejected():
    frame = _valid_frame()
    frame.loc[1, " Job ID "] = "A-1"
    with pytest.raises(SchemaValidationError, match="job_id contains duplicates"):
        preprocess_jobs(frame)


def test_clicks_cannot_exceed_views():
    frame = _valid_frame()
    frame.loc[0, "Views"] = 3
    frame.loc[0, "Clicks"] = 4
    with pytest.raises(SchemaValidationError, match="clicks exceeds views"):
        preprocess_jobs(frame)


def test_ctr_is_safe_for_zero_views_and_summary_is_weighted():
    frame = pd.DataFrame(
        {
            "job_title": ["A", "B"],
            "location": ["X", "Y"],
            "views": [10, 0],
            "clicks": [2, 0],
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "experience_level": ["junior", "unknown"],
            "skills": [["Python"], []],
        }
    )
    enriched = calculate_ctr(frame)
    assert enriched.loc[0, "ctr"] == pytest.approx(0.2)
    assert math.isnan(enriched.loc[1, "ctr"])
    summary = build_summary(enriched)
    assert summary["engagement"]["overall_ctr"] == pytest.approx(0.2)
    assert summary["engagement"]["zero_view_records"] == 1
