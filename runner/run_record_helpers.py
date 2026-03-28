"""Run-record provenance helpers for schema_version 1.

This module provides functions to capture authoritative run-time provenance
for completed benchmark runs, including completion timestamps and repository
metadata (commit SHA, branch, dirty state).
"""

import datetime as _dt
import subprocess
from pathlib import Path
from typing import Any


def _completed_at_timestamp() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_git_commit_sha(repo_root: Path | None = None) -> str | None:
    """Resolve the current git commit SHA.

    Args:
        repo_root: Path to the repository root. If None, uses current working directory.

    Returns:
        The full commit SHA, or None if it cannot be resolved.
    """
    try:
        cmd = ["git", "rev-parse", "HEAD"]
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return None
        sha = proc.stdout.strip()
        if not sha:
            return None
        return sha
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _resolve_git_branch(repo_root: Path | None = None) -> str | None:
    """Resolve the current git branch name.

    Handles both normal branch states and detached HEAD state.

    Args:
        repo_root: Path to the repository root. If None, uses current working directory.

    Returns:
        The branch name, "HEAD" for detached state, or None if it cannot be resolved.
    """
    try:
        cmd = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return None
        branch = proc.stdout.strip()
        if not branch:
            return None
        return branch
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _is_git_repo_dirty(repo_root: Path | None = None) -> bool | None:
    """Check if the git repository has uncommitted changes.

    Detects staged changes, unstaged changes, and untracked files.

    Args:
        repo_root: Path to the repository root. If None, uses current working directory.

    Returns:
        True if there are uncommitted changes, False if clean, or None if it cannot be resolved.
    """
    try:
        # Check for staged changes (cached)
        cmd = ["git", "diff", "--cached", "--quiet", "--ignore-submodules"]
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 1:
            return True
        if proc.returncode != 0:
            return None

        # Check for unstaged changes
        cmd = ["git", "diff", "--quiet", "--ignore-submodules"]
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 1:
            return True
        if proc.returncode != 0:
            return None

        # Check for untracked files (not staged)
        cmd = ["git", "ls-files", "--others", "--exclude-standard"]
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return None

        # If there are any untracked files, the repo is dirty
        untracked = proc.stdout.strip()
        if untracked:
            return True

        return False
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _collect_repo_provenance(
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Collect repository provenance metadata.

    Captures git commit SHA, branch name, and dirty state.
    All fields gracefully degrade to None when git metadata cannot be resolved.

    Args:
        repo_root: Path to the repository root. If None, uses current working directory.

    Returns:
        Dictionary containing repo_commit_sha, repo_branch, and repo_dirty fields.
    """
    if repo_root is None:
        repo_root = Path.cwd()

    return {
        "repo_commit_sha": _resolve_git_commit_sha(repo_root),
        "repo_branch": _resolve_git_branch(repo_root),
        "repo_dirty": _is_git_repo_dirty(repo_root),
    }


def build_run_record_provenance(
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Build complete run-record provenance for a completed benchmark run.

    Combines completion timestamp with repository provenance metadata
    in schema_version 1 format.

    Args:
        repo_root: Path to the repository root. If None, uses current working directory.

    Returns:
        Dictionary containing schema_version, completed_at, and repository provenance fields.
    """
    provenance: dict[str, Any] = {
        "schema_version": "1.0.0",
        "completed_at": _completed_at_timestamp(),
    }

    repo_info = _collect_repo_provenance(repo_root)
    provenance.update(repo_info)

    return provenance


def merge_run_provenance(
    result: dict[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Merge run-record provenance into an existing result dictionary.

    Adds schema_version, completed_at, and repository provenance fields
    to an existing result dict. Does not overwrite existing keys.

    Args:
        result: The existing result dictionary to merge into.
        repo_root: Path to the repository root. If None, uses current working directory.

    Returns:
        The result dictionary with provenance fields added.
    """
    provenance = build_run_record_provenance(repo_root)

    for key, value in provenance.items():
        if key not in result:
            result[key] = value

    return result
