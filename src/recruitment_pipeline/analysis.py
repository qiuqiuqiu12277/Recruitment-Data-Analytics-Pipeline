"""Metrics, summaries, and non-interactive charts."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402


def _configure_multilingual_font() -> None:
    """Prefer an installed CJK-capable font while remaining portable."""

    available = {font.name for font in font_manager.fontManager.ttflist}
    candidates = (
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Microsoft YaHei",
        "PingFang SC",
        "Arial Unicode MS",
        "Hiragino Sans GB",
        "SimHei",
    )
    selected = next((name for name in candidates if name in available), None)
    if selected:
        matplotlib.rcParams["font.sans-serif"] = [selected, "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False


_configure_multilingual_font()


def calculate_ctr(frame: pd.DataFrame) -> pd.DataFrame:
    """Add a click-through-rate column, using NaN when views are zero."""

    missing = {"views", "clicks"}.difference(frame.columns)
    if missing:
        raise ValueError("CTR requires columns: " + ", ".join(sorted(missing)))

    result = frame.copy()
    views = pd.to_numeric(result["views"], errors="coerce").astype(float)
    clicks = pd.to_numeric(result["clicks"], errors="coerce").astype(float)
    valid = views.gt(0) & clicks.notna()
    ctr = pd.Series(np.nan, index=result.index, dtype=float)
    ctr.loc[valid] = clicks.loc[valid] / views.loc[valid]
    result["ctr"] = ctr
    return result


def _iter_skills(values: Iterable[object]) -> Iterable[str]:
    for value in values:
        if isinstance(value, (list, tuple, set)):
            yield from (str(skill) for skill in value)
        elif isinstance(value, str) and value.startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                yield from (str(skill) for skill in parsed)


def _optional_round(value: float, digits: int = 6) -> float | None:
    return None if pd.isna(value) else round(float(value), digits)


def build_summary(frame: pd.DataFrame, top_n: int = 10) -> dict[str, object]:
    """Build JSON-serializable portfolio metrics from enriched records."""

    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    missing = {"views", "clicks", "ctr"}.difference(frame.columns)
    if missing:
        raise ValueError("summary requires columns: " + ", ".join(sorted(missing)))

    total_views = int(frame["views"].sum())
    total_clicks = int(frame["clicks"].sum())
    overall_ctr = total_clicks / total_views if total_views else None
    dates = pd.to_datetime(frame.get("date", pd.Series(dtype="datetime64[ns]")), errors="coerce")
    valid_dates = dates.dropna()
    skill_counts = Counter(_iter_skills(frame.get("skills", pd.Series(dtype=object))))

    levels = frame.get("experience_level", pd.Series(dtype=str)).fillna("unknown")
    level_counts = {
        level: int((levels == level).sum())
        for level in ("entry", "junior", "mid", "senior", "unknown")
    }

    return {
        "records": int(len(frame)),
        "unique_job_titles": int(frame.get("job_title", pd.Series(dtype=str)).nunique()),
        "unique_locations": int(frame.get("location", pd.Series(dtype=str)).nunique()),
        "date_range": {
            "start": valid_dates.min().date().isoformat() if not valid_dates.empty else None,
            "end": valid_dates.max().date().isoformat() if not valid_dates.empty else None,
        },
        "engagement": {
            "total_views": total_views,
            "total_clicks": total_clicks,
            "overall_ctr": _optional_round(overall_ctr) if overall_ctr is not None else None,
            "mean_posting_ctr": _optional_round(frame["ctr"].mean()),
            "median_posting_ctr": _optional_round(frame["ctr"].median()),
            "zero_view_records": int(frame["views"].eq(0).sum()),
        },
        "experience_levels": level_counts,
        "top_skills": [
            {"skill": skill, "postings": int(count)}
            for skill, count in skill_counts.most_common(top_n)
        ],
    }


def _prepare_output(output: str | Path) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _save_figure(fig: plt.Figure, output: str | Path) -> Path:
    output_path = _prepare_output(output)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_skill_frequency(frame: pd.DataFrame, output: str | Path, top_n: int = 10) -> Path:
    counts = Counter(_iter_skills(frame.get("skills", pd.Series(dtype=object))))
    values = counts.most_common(top_n)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    if values:
        labels, frequencies = zip(*reversed(values))
        ax.barh(labels, frequencies, color="#2563eb")
        ax.set_xlabel("Number of job postings")
    else:
        ax.text(0.5, 0.5, "No skills detected", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Most requested skills")
    return _save_figure(fig, output)


def plot_experience_distribution(frame: pd.DataFrame, output: str | Path) -> Path:
    order = ["entry", "junior", "mid", "senior", "unknown"]
    levels = frame.get("experience_level", pd.Series(dtype=str)).fillna("unknown")
    counts = levels.value_counts().reindex(order, fill_value=0)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(counts.index, counts.values, color="#0f766e")
    ax.set_ylabel("Number of job postings")
    ax.set_title("Experience requirements")
    return _save_figure(fig, output)


def plot_ctr_by_job_title(frame: pd.DataFrame, output: str | Path, top_n: int = 10) -> Path:
    grouped = (
        frame.groupby("job_title", dropna=False)[["clicks", "views"]]
        .sum()
        .assign(ctr=lambda values: values["clicks"].div(values["views"].replace(0, np.nan)))
        .dropna(subset=["ctr"])
        .nlargest(top_n, "ctr")
        .sort_values("ctr")
    )
    fig, ax = plt.subplots(figsize=(8, 4.8))
    if not grouped.empty:
        ax.barh(grouped.index.astype(str), grouped["ctr"], color="#ea580c")
        ax.set_xlabel("Click-through rate")
        ax.xaxis.set_major_formatter(lambda value, _position: f"{value:.0%}")
    else:
        ax.text(0.5, 0.5, "No records with views", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Weighted CTR by job title")
    return _save_figure(fig, output)


def create_charts(frame: pd.DataFrame, output_dir: str | Path, top_n: int = 10) -> list[Path]:
    """Create all standard charts and return their paths."""

    figures = Path(output_dir)
    return [
        plot_skill_frequency(frame, figures / "skill_frequency.png", top_n=top_n),
        plot_experience_distribution(frame, figures / "experience_distribution.png"),
        plot_ctr_by_job_title(frame, figures / "ctr_by_job_title.png", top_n=top_n),
    ]
