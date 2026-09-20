"""Human-review gates and tamper-evident exports for recruitment records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .pipeline import PipelineError, read_jobs_csv
from .schema import validate_job_schema

REVIEW_SCHEMA_VERSION = 1
_REVIEW_COLUMNS = {
    "record_id",
    "source_row",
    "quality_status",
    "quality_issues",
}


class WorkflowError(PipelineError):
    """Raised when review, approval, or export safeguards fail."""


@dataclass(frozen=True)
class ReviewPackageResult:
    review_queue_csv: Path
    decisions_template_csv: Path
    summary_json: Path
    records: int
    decisions_required: int


@dataclass(frozen=True)
class ApprovalResult:
    approved_csv: Path
    audit_csv: Path
    manifest_json: Path
    approved_records: int
    rejected_records: int


@dataclass(frozen=True)
class ExportResult:
    export_csv: Path
    receipt_json: Path
    records: int


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _record_id(job_id: object) -> str:
    canonical = str(job_id).strip().casefold().encode("utf-8")
    return "rec_" + hashlib.sha256(canonical).hexdigest()[:20]


def _skills_are_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    if pd.isna(value):
        return True
    text = str(value).strip()
    if not text:
        return True
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, list) and len(parsed) == 0


def _quality_issues(row: pd.Series) -> tuple[str, list[str]]:
    critical: list[str] = []
    warnings: list[str] = []
    description_value = row.get("job_description", "")
    location_value = row.get("location", "")
    description = "" if pd.isna(description_value) else str(description_value).strip()
    location = "" if pd.isna(location_value) else str(location_value).strip()

    if not description:
        critical.append("missing_job_description")
    elif len(description) < 30:
        warnings.append("short_job_description")
    if not location:
        warnings.append("missing_location")
    if int(row.get("views", 0)) == 0:
        warnings.append("zero_views")
    if "experience_level" in row.index and str(row["experience_level"]) == "unknown":
        warnings.append("experience_not_extracted")
    if "skills" in row.index and _skills_are_empty(row["skills"]):
        warnings.append("skills_not_extracted")

    issues = critical + warnings
    if critical:
        return "critical", issues
    if warnings:
        return "warning", issues
    return "clean", issues


def create_review_package(
    processed_csv: str | Path,
    output_dir: str | Path,
) -> ReviewPackageResult:
    """Annotate every record and create an explicit human-decision template."""

    source = Path(processed_csv)
    raw = read_jobs_csv(source)
    if _REVIEW_COLUMNS.intersection(raw.columns):
        raise WorkflowError("input already contains reserved review-workflow columns")
    reviewed = validate_job_schema(raw).reset_index(drop=True)
    reviewed.insert(0, "source_row", reviewed.index + 2)
    reviewed.insert(0, "record_id", reviewed["job_id"].map(_record_id))
    if reviewed["record_id"].duplicated().any():
        raise WorkflowError("generated record_id values are not unique")

    checks = reviewed.apply(_quality_issues, axis=1)
    reviewed["quality_status"] = [status for status, _ in checks]
    reviewed["quality_issues"] = [
        json.dumps(issues, ensure_ascii=False, separators=(",", ":")) for _, issues in checks
    ]
    status_counts = {
        status: int((reviewed["quality_status"] == status).sum())
        for status in ("clean", "warning", "critical")
    }
    decisions_required = status_counts["warning"] + status_counts["critical"]
    if len(reviewed) != sum(status_counts.values()):
        raise WorkflowError("row-count conservation failed while building the review queue")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    queue_path = output / "review_queue.csv"
    template_path = output / "decisions_template.csv"
    summary_path = output / "review_summary.json"
    reviewed.to_csv(queue_path, index=False, date_format="%Y-%m-%d")
    decisions = reviewed.loc[
        reviewed["quality_status"].isin(["warning", "critical"]),
        ["record_id", "job_id", "job_title", "quality_status", "quality_issues"],
    ].copy()
    decisions["decision"] = ""
    decisions["reviewer"] = ""
    decisions["note"] = ""
    decisions.to_csv(template_path, index=False)

    summary = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "created_at": _utc_timestamp(),
        "source": {"file": source.name, "sha256": _sha256_file(source)},
        "records": {
            "input": int(len(raw)),
            "review_queue": int(len(reviewed)),
            **status_counts,
            "decisions_required": decisions_required,
        },
        "invariants": {
            "row_count_conserved": len(raw) == len(reviewed) == sum(status_counts.values()),
            "every_record_has_one_quality_status": True,
        },
    }
    _write_json(summary_path, summary)
    return ReviewPackageResult(
        review_queue_csv=queue_path,
        decisions_template_csv=template_path,
        summary_json=summary_path,
        records=len(reviewed),
        decisions_required=decisions_required,
    )


def _load_decisions(path: Path, valid_ids: set[str]) -> pd.DataFrame:
    decisions = read_jobs_csv(path)
    required = {"record_id", "decision"}
    missing = required.difference(decisions.columns)
    if missing:
        raise WorkflowError("decisions file is missing columns: " + ", ".join(sorted(missing)))
    result = decisions.copy()
    result["record_id"] = result["record_id"].fillna("").astype(str).str.strip()
    result["decision"] = result["decision"].fillna("").astype(str).str.strip().str.casefold()
    result = result.loc[result["decision"].ne("")].copy()
    invalid_values = sorted(set(result["decision"]) - {"approve", "reject"})
    if invalid_values:
        raise WorkflowError(
            "decisions must be 'approve' or 'reject'; found: " + ", ".join(invalid_values)
        )
    duplicated = result["record_id"].duplicated(keep=False)
    if duplicated.any():
        values = sorted(result.loc[duplicated, "record_id"].unique().tolist())
        raise WorkflowError("duplicate decisions for record_id: " + ", ".join(values[:5]))
    unknown = sorted(set(result["record_id"]) - valid_ids)
    if unknown:
        raise WorkflowError("decisions contain unknown record_id values: " + ", ".join(unknown[:5]))
    for optional in ("reviewer", "note"):
        if optional not in result.columns:
            result[optional] = ""
        result[optional] = result[optional].fillna("").astype(str).str.strip()
    return result[["record_id", "decision", "reviewer", "note"]]


def approve_review_queue(
    review_queue_csv: str | Path,
    decisions_csv: str | Path,
    output_dir: str | Path,
) -> ApprovalResult:
    """Apply explicit decisions and emit a hash-linked approval manifest."""

    queue_path = Path(review_queue_csv)
    decisions_path = Path(decisions_csv)
    queue = read_jobs_csv(queue_path)
    missing = _REVIEW_COLUMNS.difference(queue.columns)
    if missing:
        raise WorkflowError("review queue is missing columns: " + ", ".join(sorted(missing)))
    if queue["record_id"].duplicated().any():
        raise WorkflowError("review queue contains duplicate record_id values")
    allowed_statuses = {"clean", "warning", "critical"}
    invalid_statuses = sorted(set(queue["quality_status"]) - allowed_statuses)
    if invalid_statuses:
        raise WorkflowError("review queue has invalid quality status values")

    valid_ids = set(queue["record_id"].astype(str))
    decisions = _load_decisions(decisions_path, valid_ids)
    decision_lookup = decisions.set_index("record_id") if not decisions.empty else decisions
    flagged_ids = set(
        queue.loc[queue["quality_status"].isin(["warning", "critical"]), "record_id"].astype(str)
    )
    decided_ids = set(decisions["record_id"])
    unresolved = sorted(flagged_ids - decided_ids)
    if unresolved:
        raise WorkflowError(
            f"{len(unresolved)} warning/critical records still require an explicit decision; "
            "complete the decisions template first"
        )

    audit = queue.copy()
    audit["decision"] = "approve"
    audit["reviewer"] = "automatic-clean-gate"
    audit["decision_note"] = "clean record; no manual override supplied"
    for index, row in audit.iterrows():
        record_id = str(row["record_id"])
        if record_id in decided_ids:
            decision = decision_lookup.loc[record_id]
            audit.at[index, "decision"] = decision["decision"]
            audit.at[index, "reviewer"] = decision["reviewer"]
            audit.at[index, "decision_note"] = decision["note"]
    audit["approval_status"] = audit["decision"].map({"approve": "approved", "reject": "rejected"})
    audit["decided_at"] = _utc_timestamp()
    approved = audit.loc[audit["approval_status"].eq("approved")].copy()
    rejected = audit.loc[audit["approval_status"].eq("rejected")].copy()
    if len(audit) != len(approved) + len(rejected):
        raise WorkflowError("row-count conservation failed during approval")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    approved_path = output / "approved_jobs.csv"
    audit_path = output / "approval_audit.csv"
    manifest_path = output / "approval_manifest.json"
    approved.to_csv(approved_path, index=False, date_format="%Y-%m-%d")
    audit.to_csv(audit_path, index=False, date_format="%Y-%m-%d")
    counts = {
        "review_records": int(len(queue)),
        "clean": int((queue["quality_status"] == "clean").sum()),
        "warning": int((queue["quality_status"] == "warning").sum()),
        "critical": int((queue["quality_status"] == "critical").sum()),
        "approved": int(len(approved)),
        "rejected": int(len(rejected)),
        "unresolved": 0,
    }
    manifest = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "created_at": _utc_timestamp(),
        "hash_algorithm": "sha256",
        "sources": {
            "review_queue": {"file": queue_path.name, "sha256": _sha256_file(queue_path)},
            "decisions": {"file": decisions_path.name, "sha256": _sha256_file(decisions_path)},
        },
        "artifacts": {
            "approved_jobs": {
                "file": approved_path.name,
                "sha256": _sha256_file(approved_path),
            },
            "approval_audit": {
                "file": audit_path.name,
                "sha256": _sha256_file(audit_path),
            },
        },
        "counts": counts,
        "invariants": {
            "row_count_conserved": len(queue) == len(approved) + len(rejected),
            "flagged_records_require_explicit_decision": True,
            "unresolved_records": 0,
        },
    }
    _write_json(manifest_path, manifest)
    return ApprovalResult(
        approved_csv=approved_path,
        audit_csv=audit_path,
        manifest_json=manifest_path,
        approved_records=len(approved),
        rejected_records=len(rejected),
    )


def export_approved_jobs(
    approved_csv: str | Path,
    manifest_json: str | Path,
    output_csv: str | Path,
) -> ExportResult:
    """Verify the approval manifest before exporting any record."""

    approved_path = Path(approved_csv)
    manifest_path = Path(manifest_json)
    export_path = Path(output_csv)
    if approved_path.resolve() == export_path.resolve():
        raise WorkflowError("export path must differ from the approved source file")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != REVIEW_SCHEMA_VERSION:
            raise WorkflowError("unsupported approval manifest schema version")
        if manifest.get("hash_algorithm") != "sha256":
            raise WorkflowError("approval manifest must use sha256")
        expected = manifest["artifacts"]["approved_jobs"]["sha256"]
        expected_count = int(manifest["counts"]["approved"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid approval manifest: {exc}") from exc
    actual = _sha256_file(approved_path)
    if actual != expected:
        raise WorkflowError("approved CSV hash does not match the approval manifest")

    approved = pd.read_csv(approved_path, encoding="utf-8-sig")
    if (
        "approval_status" not in approved.columns
        or not approved["approval_status"].eq("approved").all()
    ):
        raise WorkflowError("approved CSV contains records that are not approved")
    if "record_id" not in approved.columns or approved["record_id"].duplicated().any():
        raise WorkflowError("approved CSV must contain unique record_id values")
    if len(approved) != expected_count:
        raise WorkflowError("approved record count does not match the approval manifest")

    export_path.parent.mkdir(parents=True, exist_ok=True)
    approved.to_csv(export_path, index=False)
    receipt_path = export_path.with_suffix(".receipt.json")
    receipt = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "created_at": _utc_timestamp(),
        "records": int(len(approved)),
        "sources": {
            "approval_manifest_sha256": _sha256_file(manifest_path),
            "approved_jobs_sha256": actual,
        },
        "export": {"file": export_path.name, "sha256": _sha256_file(export_path)},
    }
    _write_json(receipt_path, receipt)
    return ExportResult(export_csv=export_path, receipt_json=receipt_path, records=len(approved))
