"""Deterministic cleaning for recruitment data."""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

from .schema import normalise_columns, validate_job_schema

TEXT_COLUMNS = ("job_title", "job_description", "location")


def clean_text(value: object) -> str:
    """Normalize Unicode and whitespace without changing the text's meaning."""

    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", text).strip()


def preprocess_jobs(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize headers/text, remove exact duplicates, and validate the schema."""

    result = normalise_columns(frame)
    for column in TEXT_COLUMNS:
        if column in result.columns:
            result[column] = result[column].map(clean_text)

    # Only byte-for-byte duplicate records are discarded. Conflicting duplicate
    # job IDs are retained here and reported by the schema validator.
    result = result.drop_duplicates().reset_index(drop=True)
    return validate_job_schema(result)
