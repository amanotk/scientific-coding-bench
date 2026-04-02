#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runner import publish_helpers  # noqa: E402


def _build_gh_issue_create_cmd(
    *, payload: dict[str, object], repo: str | None = None
) -> list[str]:
    title = payload.get("title")
    body = payload.get("body")
    labels = payload.get("labels")
    if not isinstance(title, str) or not title:
        raise ValueError("publication payload missing title")
    if not isinstance(body, str) or not body:
        raise ValueError("publication payload missing body")
    if not isinstance(labels, list) or not all(
        isinstance(label, str) for label in labels
    ):
        raise ValueError("publication payload missing labels")

    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    for label in labels:
        cmd.extend(["--label", label])
    if repo:
        cmd.extend(["--repo", repo])
    return cmd


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Create a GitHub issue from a completed benchmark run"
    )
    parser.add_argument("run_dir", help="Path to a completed run directory")
    parser.add_argument("--repo", default="", help="Optional owner/repo override")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the gh command instead of creating the issue",
    )
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        print(f"run directory not found or not a directory: {run_dir}", file=sys.stderr)
        return 2

    try:
        payload = publish_helpers.build_publication_payload(run_dir)
        cmd = _build_gh_issue_create_cmd(payload=payload, repo=args.repo or None)
    except (FileNotFoundError, NotADirectoryError, ValueError) as e:
        print(f"Failed to build publication issue: {e}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(subprocess.list2cmdline(cmd))
        return 0

    try:
        proc = subprocess.run(cmd, check=False, text=True)
    except FileNotFoundError as e:
        print(f"Failed to run gh: {e}", file=sys.stderr)
        return 2
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
