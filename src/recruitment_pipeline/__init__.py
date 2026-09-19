"""Recruitment data validation, enrichment, and reporting."""

from .analysis import build_summary, calculate_ctr, create_charts
from .demo import generate_synthetic_jobs
from .features import (
    DEFAULT_SKILLS,
    ExperienceRange,
    SkillExtractor,
    extract_experience_range,
    extract_features,
    extract_skills,
)
from .pipeline import PipelineResult, run_pipeline
from .preprocessing import preprocess_jobs
from .schema import SchemaValidationError, validate_job_schema

__all__ = [
    "DEFAULT_SKILLS",
    "ExperienceRange",
    "PipelineResult",
    "SchemaValidationError",
    "SkillExtractor",
    "build_summary",
    "calculate_ctr",
    "create_charts",
    "extract_experience_range",
    "extract_features",
    "extract_skills",
    "generate_synthetic_jobs",
    "preprocess_jobs",
    "run_pipeline",
    "validate_job_schema",
]

__version__ = "0.2.0"
