"""Publish-time helpers for completed benchmark run directories.

This module loads canonical ``run.json`` artifacts, validates the schema_v1
record shape, and builds a deterministic publication payload for later issue
creation.
"""

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any, Mapping


_SUPPORTED_SCHEMA_VERSION = "1.0.0"
_COMPLETED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_REPO_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

_REQUIRED_FIELDS = (
    "schema_version",
    "completed_at",
    "repo_commit_sha",
    "repo_branch",
    "repo_dirty",
    "task",
    "status",
    "score",
)


def _run_json_path(run_dir: Path) -> Path:
    return run_dir / "run.json"


def _load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"run record must be a JSON object: {path}")
    return data


def load_run_record(run_dir: Path) -> dict[str, Any]:
    """Load the canonical run.json record from a completed run directory."""

    if not run_dir.exists():
        raise FileNotFoundError(f"run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise NotADirectoryError(f"run directory is not a directory: {run_dir}")

    run_json = _run_json_path(run_dir)
    if not run_json.exists():
        raise FileNotFoundError(f"missing run.json in run directory: {run_json}")
    if not run_json.is_file():
        raise FileNotFoundError(f"missing run.json in run directory: {run_json}")

    return _load_json_object(run_json)


load_publishable_run_record = load_run_record


def _require_str_field(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"run.json field {field_name!r} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"run.json field {field_name!r} must not be empty")
    return text


def _require_bool_field(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"run.json field {field_name!r} must be a boolean")
    return value


def _require_numeric_field(record: Mapping[str, Any], field_name: str) -> int | float:
    value = record.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"run.json field {field_name!r} must be numeric")
    return value


def _validate_completed_at(completed_at: str) -> None:
    if not _COMPLETED_AT_RE.fullmatch(completed_at):
        raise ValueError(
            "run.json field 'completed_at' must use UTC ISO-8601 format "
            "YYYY-MM-DDTHH:MM:SSZ"
        )
    _dt.datetime.strptime(completed_at, "%Y-%m-%dT%H:%M:%SZ")


def _normalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    schema_version = _require_str_field(record, "schema_version")
    if schema_version != _SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported run.json schema_version {schema_version!r}; "
            f"expected {_SUPPORTED_SCHEMA_VERSION!r}"
        )

    completed_at = _require_str_field(record, "completed_at")
    _validate_completed_at(completed_at)

    repo_commit_sha = _require_str_field(record, "repo_commit_sha").lower()
    if not _REPO_COMMIT_SHA_RE.fullmatch(repo_commit_sha):
        raise ValueError(
            "run.json field 'repo_commit_sha' must be a 40-character hex sha"
        )

    repo_branch = _require_str_field(record, "repo_branch")
    repo_dirty = _require_bool_field(record, "repo_dirty")
    task_ref = _require_str_field(record, "task")
    status = _require_str_field(record, "status")
    score = _require_numeric_field(record, "score")

    normalized: dict[str, Any] = dict(record)
    normalized["schema_version"] = schema_version
    normalized["completed_at"] = completed_at
    normalized["repo_commit_sha"] = repo_commit_sha
    normalized["repo_branch"] = repo_branch
    normalized["repo_dirty"] = repo_dirty
    normalized["task"] = task_ref
    normalized["status"] = status
    normalized["score"] = score
    return normalized


def validate_run_record(record: Mapping[str, Any]) -> list[str]:
    """Validate a run record and return non-blocking publication warnings."""

    for field_name in _REQUIRED_FIELDS:
        if field_name not in record:
            raise ValueError(f"run.json is missing required field {field_name!r}")

    normalized = _normalize_record(record)
    warnings: list[str] = []
    status = normalized["status"].strip().lower()
    if normalized["repo_dirty"]:
        warnings.append("repository had uncommitted changes at completion time")
    if status != "passed":
        warnings.append(f"run status is {normalized['status']!r}; mark as experimental")
    return warnings


validate_publishable_run_record = validate_run_record


def _publication_signals(record: Mapping[str, Any]) -> list[str]:
    signals: list[str] = []
    if record["repo_dirty"]:
        signals.append("repo_dirty")
    if record["status"].strip().lower() != "passed":
        signals.append("non_passing_status")
    return signals


def _issue_labels(record: Mapping[str, Any]) -> list[str]:
    labels = {"benchmark-result", "schema-v1", f"status-{_slugify(record['status'])}"}
    if _publication_signals(record):
        labels.add("experimental")
    if record["repo_dirty"]:
        labels.add("repo-dirty")
    return sorted(labels)


def _slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "unknown"


def _issue_title(record: Mapping[str, Any]) -> str:
    title = f"[{record['status']}] {record['task']}"
    repo_commit_sha = record.get("repo_commit_sha")
    if isinstance(repo_commit_sha, str) and repo_commit_sha:
        title = f"{title} @ {repo_commit_sha[:12]}"
    return title


def render_publication_body(payload: Mapping[str, Any]) -> str:
    """Render a stable, machine-readable issue body payload."""

    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


render_issue_body = render_publication_body


def build_publication_payload(run_dir: Path) -> dict[str, Any]:
    """Build a deterministic issue payload from a completed run directory."""

    record = load_run_record(run_dir)
    warnings = validate_run_record(record)
    normalized = _normalize_record(record)
    labels = _issue_labels(normalized)
    title = _issue_title(normalized)
    signals = _publication_signals(normalized)

    body_payload: dict[str, Any] = {
        "schema_version": _SUPPORTED_SCHEMA_VERSION,
        "issue": {
            "title": title,
            "labels": labels,
        },
        "publication": {
            "eligible": True,
            "signals": signals,
            "warnings": warnings,
        },
        "run_record": normalized,
    }

    return {
        "title": title,
        "labels": labels,
        "body_payload": body_payload,
        "body": render_publication_body(body_payload),
        "warnings": warnings,
        "signals": signals,
        "eligible": True,
        "run_record": normalized,
    }


build_issue_payload = build_publication_payload
