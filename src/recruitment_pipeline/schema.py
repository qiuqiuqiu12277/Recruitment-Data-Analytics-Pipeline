"""Input schema validation for recruitment records."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = (
    "job_id",
    "job_title",
    "job_description",
    "location",
    "views",
    "clicks",
    "date",
)

_COLUMN_ALIASES: dict[str, str] = {
    "job id": "job_id",
    "job title": "job_title",
    "job description": "job_description",
    "职位id": "job_id",
    "职位编号": "job_id",
    "职位名称": "job_title",
    "职位": "job_title",
    "职位描述": "job_description",
    "岗位描述": "job_description",
    "城市": "location",
    "地点": "location",
    "浏览量": "views",
    "曝光量": "views",
    "点击量": "clicks",
    "日期": "date",
}


class SchemaValidationError(ValueError):
    """Raised when the input data does not satisfy the recruitment schema."""

    def __init__(self, errors: Iterable[str]):
        self.errors = list(errors)
        super().__init__("Invalid recruitment data: " + "; ".join(self.errors))


def normalise_column_name(value: object) -> str:
    """Convert a column label to the package's canonical snake_case form."""

    text = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    if text in _COLUMN_ALIASES:
        return _COLUMN_ALIASES[text]
    text = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE).strip("_")
    return _COLUMN_ALIASES.get(text, text)


def normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with canonical column names and reject collisions."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")

    columns = [normalise_column_name(column) for column in frame.columns]
    duplicates = sorted({name for name in columns if columns.count(name) > 1})
    if duplicates:
        raise SchemaValidationError(
            ["columns become duplicated after normalisation: " + ", ".join(duplicates)]
        )

    result = frame.copy()
    result.columns = columns
    return result


def _preview_rows(mask: pd.Series, limit: int = 5) -> str:
    rows: list[str] = [str(value) for value in mask.index[mask].tolist()[:limit]]
    return ", ".join(rows)


def validate_job_schema(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and type a recruitment data frame.

    The returned frame has integer ``views``/``clicks`` columns, a normalized
    ``date`` column, and string job identifiers. All errors are collected so a
    caller can fix the input in one pass.
    """

    result = normalise_columns(frame)
    errors: list[str] = []

    missing = [column for column in REQUIRED_COLUMNS if column not in result.columns]
    if missing:
        raise SchemaValidationError(["missing required columns: " + ", ".join(missing)])

    for column in ("job_id", "job_title"):
        values = result[column].fillna("").astype(str).str.strip()
        invalid = values.eq("")
        if invalid.any():
            errors.append(f"{column} is empty at rows {_preview_rows(invalid)}")

    identifiers = result["job_id"].fillna("").astype(str).str.strip()
    duplicated_ids = identifiers.duplicated(keep=False) & identifiers.ne("")
    if duplicated_ids.any():
        duplicate_values = sorted(identifiers[duplicated_ids].unique().tolist())[:5]
        errors.append("job_id contains duplicates: " + ", ".join(duplicate_values))

    numeric_values: dict[str, pd.Series] = {}
    for column in ("views", "clicks"):
        converted = pd.to_numeric(result[column], errors="coerce")
        invalid = converted.isna() | ~np.isfinite(converted.astype(float))
        if invalid.any():
            errors.append(f"{column} is not numeric at rows {_preview_rows(invalid)}")
            continue
        negative = converted.lt(0)
        if negative.any():
            errors.append(f"{column} is negative at rows {_preview_rows(negative)}")
        fractional = converted.mod(1).ne(0)
        if fractional.any():
            errors.append(
                f"{column} must contain whole numbers at rows {_preview_rows(fractional)}"
            )
        numeric_values[column] = converted

    parsed_dates = pd.to_datetime(result["date"], errors="coerce")
    invalid_dates = parsed_dates.isna()
    if invalid_dates.any():
        errors.append(f"date is invalid at rows {_preview_rows(invalid_dates)}")

    if "views" in numeric_values and "clicks" in numeric_values:
        impossible_ctr = numeric_values["clicks"] > numeric_values["views"]
        if impossible_ctr.any():
            errors.append("clicks exceeds views at rows " + _preview_rows(impossible_ctr))

    if errors:
        raise SchemaValidationError(errors)

    result["job_id"] = identifiers
    result["views"] = numeric_values["views"].astype("int64")
    result["clicks"] = numeric_values["clicks"].astype("int64")
    result["date"] = parsed_dates.dt.normalize()
    return result
