"""Unit tests for runner/run_record_helpers.py."""

import datetime as _dt
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _load_run_record_helpers():
    """Load the run_record_helpers module."""
    import importlib.util

    repo_root = Path(__file__).resolve().parents[1]
    helpers_py = repo_root / "runner" / "run_record_helpers.py"
    spec = importlib.util.spec_from_file_location(
        "simbench_run_record_helpers", helpers_py
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


run_record_helpers = _load_run_record_helpers()


class TestCompletedAtTimestamp(unittest.TestCase):
    def test_returns_iso8601_utc_format(self):
        timestamp = run_record_helpers._completed_at_timestamp()
        self.assertRegex(timestamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_returns_recent_timestamp(self):
        timestamp = run_record_helpers._completed_at_timestamp()
        parsed = _dt.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
        now = _dt.datetime.now(_dt.timezone.utc)
        delta = abs((now - parsed).total_seconds())
        self.assertLess(delta, 5)


class TestResolveGitCommitSha(unittest.TestCase):
    def test_returns_sha_in_clean_repo(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            subprocess.run(["git", "init"], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=td_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=td_path,
                capture_output=True,
            )
            (td_path / "test.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=td_path,
                capture_output=True,
            )

            sha = run_record_helpers._resolve_git_commit_sha(td_path)
            self.assertIsNotNone(sha)
            self.assertRegex(sha, r"^[0-9a-f]{40}$")

    def test_returns_none_when_not_a_repo(self):
        with tempfile.TemporaryDirectory() as td:
            sha = run_record_helpers._resolve_git_commit_sha(Path(td))
            self.assertIsNone(sha)

    def test_returns_none_when_git_not_available(self):
        with mock.patch.object(
            run_record_helpers.subprocess,
            "run",
            side_effect=FileNotFoundError("git not found"),
        ):
            sha = run_record_helpers._resolve_git_commit_sha()
            self.assertIsNone(sha)

    def test_returns_none_on_subprocess_failure(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch(
                "subprocess.run",
                side_effect=OSError("simulated failure"),
            ):
                sha = run_record_helpers._resolve_git_commit_sha(Path(td))
                self.assertIsNone(sha)


class TestResolveGitBranch(unittest.TestCase):
    def test_returns_branch_name_in_clean_repo(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            subprocess.run(["git", "init"], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=td_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=td_path,
                capture_output=True,
            )
            (td_path / "test.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=td_path,
                capture_output=True,
            )

            branch = run_record_helpers._resolve_git_branch(td_path)
            # Default branch could be main or master depending on git version
            self.assertIn(branch, ("main", "master"))

    def test_returns_head_in_detached_state(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            subprocess.run(["git", "init"], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=td_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=td_path,
                capture_output=True,
            )
            (td_path / "test.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=td_path,
                capture_output=True,
            )
            # First commit creates HEAD, so HEAD~1 would fail.
            # Instead create a second commit and checkout to detach
            (td_path / "test2.txt").write_text("content2\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "second"],
                cwd=td_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "checkout", "--detach", "HEAD~1"],
                cwd=td_path,
                capture_output=True,
            )

            branch = run_record_helpers._resolve_git_branch(td_path)
            self.assertEqual(branch, "HEAD")

    def test_returns_none_when_not_a_repo(self):
        with tempfile.TemporaryDirectory() as td:
            branch = run_record_helpers._resolve_git_branch(Path(td))
            self.assertIsNone(branch)

    def test_returns_none_when_git_not_available(self):
        with mock.patch.object(
            run_record_helpers.subprocess,
            "run",
            side_effect=FileNotFoundError("git not found"),
        ):
            branch = run_record_helpers._resolve_git_branch()
            self.assertIsNone(branch)


class TestIsGitRepoDirty(unittest.TestCase):
    def test_returns_false_in_clean_repo(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            subprocess.run(["git", "init"], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=td_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=td_path,
                capture_output=True,
            )
            (td_path / "test.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=td_path,
                capture_output=True,
            )

            dirty = run_record_helpers._is_git_repo_dirty(td_path)
            self.assertEqual(dirty, False)

    def test_returns_true_with_uncommitted_changes(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            subprocess.run(["git", "init"], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=td_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=td_path,
                capture_output=True,
            )
            (td_path / "test.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=td_path,
                capture_output=True,
            )
            (td_path / "new.txt").write_text("new content\n", encoding="utf-8")

            dirty = run_record_helpers._is_git_repo_dirty(td_path)
            self.assertEqual(dirty, True)

    def test_returns_true_with_staged_changes(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            subprocess.run(["git", "init"], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=td_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=td_path,
                capture_output=True,
            )
            (td_path / "test.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=td_path,
                capture_output=True,
            )
            (td_path / "test.txt").write_text("modified\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=td_path, capture_output=True)

            dirty = run_record_helpers._is_git_repo_dirty(td_path)
            self.assertEqual(dirty, True)

    def test_returns_none_when_not_a_repo(self):
        with tempfile.TemporaryDirectory() as td:
            dirty = run_record_helpers._is_git_repo_dirty(Path(td))
            self.assertIsNone(dirty)

    def test_returns_none_when_git_not_available(self):
        with mock.patch.object(
            run_record_helpers.subprocess,
            "run",
            side_effect=FileNotFoundError("git not found"),
        ):
            dirty = run_record_helpers._is_git_repo_dirty()
            self.assertIsNone(dirty)

    def test_returns_none_on_subprocess_failure(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch(
                "subprocess.run",
                side_effect=OSError("simulated failure"),
            ):
                dirty = run_record_helpers._is_git_repo_dirty(Path(td))
                self.assertIsNone(dirty)


class TestCollectRepoProvenance(unittest.TestCase):
    def test_returns_all_fields_in_clean_repo(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            subprocess.run(["git", "init"], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=td_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=td_path,
                capture_output=True,
            )
            (td_path / "test.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=td_path,
                capture_output=True,
            )

            result = run_record_helpers._collect_repo_provenance(td_path)
            self.assertIn("repo_commit_sha", result)
            self.assertIn("repo_branch", result)
            self.assertIn("repo_dirty", result)
            self.assertIsNotNone(result["repo_commit_sha"])
            # Default branch could be main or master depending on git version
            self.assertIn(result["repo_branch"], ("main", "master"))
            self.assertEqual(result["repo_dirty"], False)

    def test_returns_none_fields_when_not_a_repo(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_record_helpers._collect_repo_provenance(Path(td))
            self.assertIsNone(result["repo_commit_sha"])
            self.assertIsNone(result["repo_branch"])
            self.assertIsNone(result["repo_dirty"])

    def test_defaults_to_cwd_when_repo_root_is_none(self):
        with mock.patch("pathlib.Path.cwd", return_value=Path("/nonexistent")):
            result = run_record_helpers._collect_repo_provenance(None)
            self.assertIsNone(result["repo_commit_sha"])
            self.assertIsNone(result["repo_branch"])
            self.assertIsNone(result["repo_dirty"])


class TestBuildRunRecordProvenance(unittest.TestCase):
    def test_includes_schema_version(self):
        provenance = run_record_helpers.build_run_record_provenance()
        self.assertEqual(provenance["schema_version"], "1.0.0")

    def test_includes_completed_at_timestamp(self):
        provenance = run_record_helpers.build_run_record_provenance()
        self.assertIn("completed_at", provenance)
        self.assertRegex(
            provenance["completed_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        )

    def test_includes_repo_provenance_fields(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            subprocess.run(["git", "init"], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=td_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=td_path,
                capture_output=True,
            )
            (td_path / "test.txt").write_text("content\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=td_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=td_path,
                capture_output=True,
            )

            provenance = run_record_helpers.build_run_record_provenance(td_path)
            self.assertIn("repo_commit_sha", provenance)
            self.assertIn("repo_branch", provenance)
            self.assertIn("repo_dirty", provenance)


class TestMergeRunProvenance(unittest.TestCase):
    def test_adds_provenance_to_empty_result(self):
        result: dict = {}
        merged = run_record_helpers.merge_run_provenance(result)

        self.assertIn("schema_version", merged)
        self.assertIn("completed_at", merged)
        self.assertIn("repo_commit_sha", merged)
        self.assertIn("repo_branch", merged)
        self.assertIn("repo_dirty", merged)

    def test_does_not_overwrite_existing_keys(self):
        result = {
            "schema_version": "2.0.0",
            "completed_at": "2024-01-01T00:00:00Z",
            "run_id": "test-123",
        }
        merged = run_record_helpers.merge_run_provenance(result)

        self.assertEqual(merged["schema_version"], "2.0.0")
        self.assertEqual(merged["completed_at"], "2024-01-01T00:00:00Z")
        self.assertEqual(merged["run_id"], "test-123")

    def test_preserves_other_existing_fields(self):
        result = {
            "run_id": "test-123",
            "task": "s/t",
            "status": "passed",
            "score": 1.0,
        }
        merged = run_record_helpers.merge_run_provenance(result)

        self.assertEqual(merged["run_id"], "test-123")
        self.assertEqual(merged["task"], "s/t")
        self.assertEqual(merged["status"], "passed")
        self.assertEqual(merged["score"], 1.0)
        self.assertIn("schema_version", merged)


if __name__ == "__main__":
    unittest.main()
