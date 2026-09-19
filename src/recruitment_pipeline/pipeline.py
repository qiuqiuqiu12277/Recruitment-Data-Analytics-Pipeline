"""End-to-end recruitment analytics pipeline."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .analysis import build_summary, calculate_ctr, create_charts
from .features import DEFAULT_SKILLS, SkillExtractor, extract_features, load_skill_config
from .preprocessing import preprocess_jobs


class PipelineError(RuntimeError):
    """Raised when an input file cannot be read or an output cannot be produced."""


@dataclass(frozen=True)
class PipelineResult:
    processed_csv: Path
    summary_json: Path
    chart_paths: list[Path]
    records: int


def read_jobs_csv(path: str | Path) -> pd.DataFrame:
    """Read UTF-8 CSV data, with a GB18030 fallback for Chinese exports."""

    input_path = Path(path)
    if not input_path.is_file():
        raise PipelineError(f"input file does not exist: {input_path}")
    try:
        return pd.read_csv(input_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            return pd.read_csv(input_path, encoding="gb18030")
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            raise PipelineError(f"could not decode CSV file {input_path}: {exc}") from exc
    except pd.errors.EmptyDataError as exc:
        raise PipelineError(f"input CSV is empty: {input_path}") from exc
    except pd.errors.ParserError as exc:
        raise PipelineError(f"could not parse CSV file {input_path}: {exc}") from exc


def enrich_jobs(frame: pd.DataFrame, extractor: SkillExtractor | None = None) -> pd.DataFrame:
    """Add structured description features and a safe CTR column."""

    skill_extractor = extractor or SkillExtractor(DEFAULT_SKILLS)
    records = [extract_features(text, skill_extractor) for text in frame["job_description"]]
    feature_columns = (
        "experience_min_years",
        "experience_max_years",
        "experience_level",
        "skills",
    )
    features = pd.DataFrame.from_records(records, columns=feature_columns, index=frame.index)
    return calculate_ctr(pd.concat([frame, features], axis=1))


def _resolve_extractor(
    skills_config: str | Path | Mapping[str, Sequence[str]] | None,
) -> SkillExtractor:
    if skills_config is None:
        return SkillExtractor(DEFAULT_SKILLS)
    if isinstance(skills_config, (str, Path)):
        return SkillExtractor(load_skill_config(skills_config))
    return SkillExtractor(skills_config)


def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    skills_config: str | Path | Mapping[str, Sequence[str]] | None = None,
    top_n: int = 10,
    include_charts: bool = True,
) -> PipelineResult:
    """Run validation, feature extraction, metrics, and reporting."""

    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    raw = read_jobs_csv(input_path)
    cleaned = preprocess_jobs(raw)
    enriched = enrich_jobs(cleaned, _resolve_extractor(skills_config))

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    processed_path = destination / "processed_jobs.csv"
    summary_path = destination / "summary.json"

    export = enriched.copy()
    export["skills"] = export["skills"].map(
        lambda skills: json.dumps(skills, ensure_ascii=False, separators=(",", ":"))
    )
    export.to_csv(processed_path, index=False, date_format="%Y-%m-%d")

    summary = build_summary(enriched, top_n=top_n)
    summary["data_quality"] = {
        "input_records": int(len(raw)),
        "records_after_cleaning": int(len(cleaned)),
        "exact_duplicates_removed": int(len(raw) - len(cleaned)),
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    chart_paths = (
        create_charts(enriched, destination / "figures", top_n=top_n) if include_charts else []
    )
    return PipelineResult(
        processed_csv=processed_path,
        summary_json=summary_path,
        chart_paths=chart_paths,
        records=len(enriched),
    )
