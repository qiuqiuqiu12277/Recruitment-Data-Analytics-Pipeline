"""Deterministic, privacy-safe synthetic data for demonstrations."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

_TEMPLATES: tuple[dict[str, object], ...] = (
    {
        "job_title": "Data Analyst",
        "description": "1-3 years of experience with Python, SQL, pandas and Excel.",
        "rate": 0.13,
    },
    {
        "job_title": "Machine Learning Engineer",
        "description": "At least 3 years in machine learning; Python, PyTorch and Spark required.",
        "rate": 0.16,
    },
    {
        "job_title": "Software Engineer",
        "description": "5+ years building services with Java, SQL and JavaScript.",
        "rate": 0.11,
    },
    {
        "job_title": "Quantitative Analyst",
        "description": "2 to 4 years using Python, NumPy, R and statistical modelling.",
        "rate": 0.17,
    },
    {
        "job_title": "商业数据分析师",
        "description": "要求三至五年数据分析经验，熟练使用 SQL、Python、Tableau 和 Power BI。",
        "rate": 0.14,
    },
    {
        "job_title": "算法工程师",
        "description": "至少2年机器学习经验，掌握 Python、深度学习、TensorFlow。",
        "rate": 0.15,
    },
    {
        "job_title": "Research Assistant",
        "description": "Fresh graduate welcome; Python and Excel skills preferred.",
        "rate": 0.18,
    },
    {
        "job_title": "数据实习生",
        "description": "应届生可申请，无需经验；会 SQL、Python 或电子表格者优先。",
        "rate": 0.20,
    },
)

_LOCATIONS = ("Shanghai", "Beijing", "Hangzhou", "Shenzhen", "Ningbo", "Remote")


def generate_synthetic_jobs(rows: int = 100, seed: int = 42) -> pd.DataFrame:
    """Generate realistic-looking records that contain no personal data."""

    if rows < 1:
        raise ValueError("rows must be at least 1")

    rng = np.random.default_rng(seed)
    records: list[dict[str, object]] = []
    start_date = pd.Timestamp("2026-01-01")
    for offset in range(rows):
        template = _TEMPLATES[int(rng.integers(0, len(_TEMPLATES)))]
        views = 0 if rng.random() < 0.04 else int(rng.integers(250, 2501))
        clicks = int(rng.binomial(views, float(template["rate"]))) if views else 0
        records.append(
            {
                "job_id": f"DEMO-{offset + 1:05d}",
                "job_title": template["job_title"],
                "job_description": template["description"],
                "location": str(rng.choice(_LOCATIONS)),
                "views": views,
                "clicks": clicks,
                "date": (start_date + pd.Timedelta(days=int(rng.integers(0, 90))))
                .date()
                .isoformat(),
            }
        )
    return pd.DataFrame.from_records(records)


def write_synthetic_jobs(output: str | Path, rows: int = 100, seed: int = 42) -> Path:
    """Generate a demo CSV and return its path."""

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_synthetic_jobs(rows=rows, seed=seed).to_csv(output_path, index=False)
    return output_path
