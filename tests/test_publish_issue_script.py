import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


def _load_publish_issue_script():
    repo_root = Path(__file__).resolve().parents[1]
    script_py = repo_root / "scripts" / "publish_issue.py"
    spec = importlib.util.spec_from_file_location("simbench_publish_issue", script_py)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


publish_issue = _load_publish_issue_script()


def _write_run_record(run_dir: Path, record: dict[str, object]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _valid_run_record() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "completed_at": "2026-03-28T12:34:56Z",
        "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
        "repo_branch": "main",
        "repo_dirty": False,
        "task": "suite/task",
        "status": "passed",
        "score": 1.0,
    }


class TestPublishIssueScript(unittest.TestCase):
    def test_build_gh_issue_create_cmd_uses_generated_labels(self):
        cmd = publish_issue._build_gh_issue_create_cmd(
            payload={
                "title": "[result] [passed] suite/task @ abcdef123456",
                "body": "{}\n",
                "labels": ["result", "schema-v1", "status:passed", "track:official"],
            },
            repo="amanotk/simbench",
        )

        self.assertEqual(cmd[:4], ["gh", "issue", "create", "--title"])
        self.assertIn("[result] [passed] suite/task @ abcdef123456", cmd)
        self.assertIn("--body", cmd)
        self.assertEqual(cmd.count("--label"), 4)
        self.assertEqual(cmd[-2:], ["--repo", "amanotk/simbench"])

    def test_main_dry_run_prints_gh_command(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            _write_run_record(run_dir, _valid_run_record())

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = publish_issue.main([str(run_dir), "--dry-run"])

            self.assertEqual(rc, 0)
            self.assertEqual(err.getvalue(), "")
            command = out.getvalue()
            self.assertIn("gh issue create", command)
            self.assertIn("--label result", command)
            self.assertIn("--label schema-v1", command)
            self.assertIn("--label status:passed", command)
            self.assertIn("--label track:official", command)
            self.assertIn("[result] [passed] suite/task @ abcdef123456", command)

    def test_main_runs_gh_issue_create(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            _write_run_record(run_dir, _valid_run_record())
            captured: dict[str, object] = {}

            def _fake_run(cmd, **kwargs):
                captured["cmd"] = cmd
                captured["kwargs"] = kwargs
                return mock.Mock(returncode=0)

            with mock.patch("subprocess.run", side_effect=_fake_run):
                rc = publish_issue.main([str(run_dir), "--repo", "amanotk/simbench"])

            self.assertEqual(rc, 0)
            cmd = captured["cmd"]
            assert isinstance(cmd, list)
            self.assertIn("--repo", cmd)
            self.assertIn("amanotk/simbench", cmd)
            self.assertEqual(cmd.count("--label"), 4)
