"""Unit tests for runner/publish_helpers.py."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_publish_helpers():
    repo_root = Path(__file__).resolve().parents[1]
    helpers_py = repo_root / "runner" / "publish_helpers.py"
    spec = importlib.util.spec_from_file_location(
        "simbench_publish_helpers", helpers_py
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


publish_helpers = _load_publish_helpers()


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
        "run_id": "run-123",
        "started_at": "2026-03-28T12:30:00Z",
        "agent": "dummy",
        "model": "provider/model",
        "metrics": {"eval_seconds": 1.25},
    }


class TestPublishHelpers(unittest.TestCase):
    def test_build_publication_payload_returns_stable_publishable_payload(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            _write_run_record(run_dir, _valid_run_record())

            payload_one = publish_helpers.build_publication_payload(run_dir)
            payload_two = publish_helpers.build_publication_payload(run_dir)

            self.assertEqual(payload_one, payload_two)
            self.assertEqual(
                payload_one["title"],
                "[result] [passed] suite/task @ abcdef123456",
            )
            self.assertEqual(
                payload_one["labels"],
                ["result", "schema-v1", "status:passed", "track:official"],
            )
            self.assertEqual(payload_one["warnings"], [])
            self.assertEqual(payload_one["signals"], [])
            self.assertTrue(payload_one["eligible"])

            rendered_body = payload_one["body"]
            self.assertEqual(rendered_body, payload_two["body"])
            self.assertTrue(rendered_body.endswith("\n"))
            parsed_body = json.loads(rendered_body)
            self.assertEqual(parsed_body, payload_one["body_payload"])
            self.assertEqual(parsed_body["run_record"]["task"], "suite/task")

    def test_build_publication_payload_marks_experimental_runs(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["repo_dirty"] = True
            record["status"] = "failed"
            record["score"] = 0.0
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)

            self.assertIn("track:experimental", payload["labels"])
            self.assertTrue(payload["signals"])
            self.assertIn("repository had uncommitted changes", payload["warnings"][0])
            self.assertIn("mark as experimental", payload["warnings"][1])

    def test_missing_run_json_raises_file_not_found_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            with self.assertRaises(FileNotFoundError):
                publish_helpers.build_publication_payload(run_dir)

    def test_malformed_run_json_raises_json_decode_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text("{not json", encoding="utf-8")

            with self.assertRaises(json.JSONDecodeError):
                publish_helpers.build_publication_payload(run_dir)

    def test_unsupported_schema_version_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["schema_version"] = "2.0.0"
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError):
                publish_helpers.build_publication_payload(run_dir)

    def test_missing_required_fields_raise_value_error(self):
        required_fields = [
            "schema_version",
            "completed_at",
            "repo_commit_sha",
            "repo_branch",
            "repo_dirty",
            "task",
            "status",
            "score",
        ]

        for field_name in required_fields:
            with self.subTest(field_name=field_name):
                with tempfile.TemporaryDirectory() as td:
                    run_dir = Path(td)
                    record = _valid_run_record()
                    record.pop(field_name)
                    _write_run_record(run_dir, record)

                    with self.assertRaises(ValueError):
                        publish_helpers.build_publication_payload(run_dir)

    def test_payload_rendering_is_stable_across_input_key_order(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir_a = Path(td) / "a"
            run_dir_b = Path(td) / "b"

            record_a = _valid_run_record()
            record_b = {
                "score": 1.0,
                "status": "passed",
                "task": "suite/task",
                "repo_dirty": False,
                "repo_branch": "main",
                "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                "completed_at": "2026-03-28T12:34:56Z",
                "schema_version": "1.0.0",
                "run_id": "run-123",
                "started_at": "2026-03-28T12:30:00Z",
                "metrics": {"eval_seconds": 1.25},
                "model": "provider/model",
                "agent": "dummy",
            }

            _write_run_record(run_dir_a, record_a)
            _write_run_record(run_dir_b, record_b)

            payload_a = publish_helpers.build_publication_payload(run_dir_a)
            payload_b = publish_helpers.build_publication_payload(run_dir_b)

            self.assertEqual(payload_a["body"], payload_b["body"])
            self.assertEqual(payload_a["labels"], payload_b["labels"])
            self.assertEqual(payload_a["title"], payload_b["title"])

    # Additional tests for Task 2.1: validation and payload generation

    def test_load_run_record_returns_record_from_valid_directory(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            _write_run_record(run_dir, record)

            loaded = publish_helpers.load_run_record(run_dir)

            self.assertEqual(loaded["schema_version"], "1.0.0")
            self.assertEqual(loaded["task"], "suite/task")
            self.assertEqual(loaded["status"], "passed")

    def test_load_run_record_nonexistent_directory_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "nonexistent"

            with self.assertRaises(FileNotFoundError):
                publish_helpers.load_run_record(run_dir)

    def test_load_run_record_not_a_directory_raises_not_adirectory(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "file.json"
            run_dir.write_text("{}", encoding="utf-8")

            with self.assertRaises(NotADirectoryError):
                publish_helpers.load_run_record(run_dir)

    def test_load_run_record_missing_run_json_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            run_dir.mkdir(parents=True, exist_ok=True)

            with self.assertRaises(FileNotFoundError):
                publish_helpers.load_run_record(run_dir)

    def test_validate_run_record_returns_warnings_for_dirty_repo(self):
        record = _valid_run_record()
        record["repo_dirty"] = True

        warnings = publish_helpers.validate_run_record(record)

        self.assertIn("repository had uncommitted changes at completion time", warnings)

    def test_validate_run_record_returns_warnings_for_non_passing_status(self):
        record = _valid_run_record()
        record["status"] = "failed"

        warnings = publish_helpers.validate_run_record(record)

        self.assertIn("run status is 'failed'; mark as experimental", warnings)

    def test_validate_run_record_returns_empty_list_for_clean_passing_run(self):
        record = _valid_run_record()
        # Already clean and passing from _valid_run_record()

        warnings = publish_helpers.validate_run_record(record)

        self.assertEqual(warnings, [])

    def test_build_publication_payload_allows_null_repo_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["repo_commit_sha"] = None
            record["repo_branch"] = None
            record["repo_dirty"] = None
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)

            self.assertEqual(payload["title"], "[result] [passed] suite/task")
            self.assertIn("track:experimental", payload["labels"])
            self.assertIn("repo_commit_sha_missing", payload["signals"])
            self.assertIn("repo_branch_missing", payload["signals"])
            self.assertIn("repo_dirty_unknown", payload["signals"])
            self.assertIn(
                "repository commit sha could not be resolved at completion time",
                payload["warnings"],
            )
            self.assertIn(
                "repository branch could not be resolved at completion time",
                payload["warnings"],
            )
            self.assertIn(
                "repository dirty state could not be resolved at completion time",
                payload["warnings"],
            )

    def test_validate_run_record_rejects_invalid_nullable_repo_provenance_types(self):
        for field_name, bad_value in (
            ("repo_commit_sha", 123),
            ("repo_branch", 123),
            ("repo_dirty", "false"),
        ):
            with self.subTest(field_name=field_name):
                record = _valid_run_record()
                record[field_name] = bad_value

                with self.assertRaises(ValueError):
                    publish_helpers.validate_run_record(record)

    def test_render_publication_body_returns_sorted_json_with_newline(self):
        payload = {
            "schema_version": "1.0.0",
            "run_record": {"score": 1.0, "task": "demo/test"},
        }

        body = publish_helpers.render_publication_body(payload)

        self.assertTrue(body.endswith("\n"))
        parsed = json.loads(body)
        self.assertEqual(parsed, payload)
        # Verify keys are sorted
        self.assertIn('"run_record"', body)
        self.assertIn('"schema_version"', body)

    def test_invalid_completed_at_format_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["completed_at"] = "2026/03/28 12:34:56"  # Wrong format
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("completed_at", str(ctx.exception))

    def test_invalid_completed_at_invalid_date_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["completed_at"] = "2026-13-45T99:99:99Z"  # Invalid date/time
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError):
                publish_helpers.build_publication_payload(run_dir)

    def test_invalid_repo_commit_sha_wrong_length_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["repo_commit_sha"] = "abc123"  # Too short
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("repo_commit_sha", str(ctx.exception))

    def test_invalid_repo_commit_sha_non_hex_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["repo_commit_sha"] = (
                "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"  # Non-hex
            )
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("repo_commit_sha", str(ctx.exception))

    def test_empty_string_field_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["repo_branch"] = "   "  # Whitespace only
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("repo_branch", str(ctx.exception))

    def test_wrong_field_type_string_for_boolean_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["repo_dirty"] = "true"  # Should be boolean
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("repo_dirty", str(ctx.exception))

    def test_wrong_field_type_number_for_string_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["status"] = 123  # Should be string
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("status", str(ctx.exception))

    def test_wrong_field_type_boolean_for_number_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["score"] = True  # Should be numeric
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("score", str(ctx.exception))

    def test_non_passing_status_in_issue_labels(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["status"] = "Failed"  # Different case

            _write_run_record(run_dir, record)
            payload = publish_helpers.build_publication_payload(run_dir)

            self.assertIn("status:failed", payload["labels"])

    def test_sluggified_status_with_special_characters(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["status"] = "Failed (with issues)"

            _write_run_record(run_dir, record)
            payload = publish_helpers.build_publication_payload(run_dir)

            self.assertIn("status:error", payload["labels"])

    def test_missing_repo_commit_sha_is_required_field_error(self):
        """repo_commit_sha is a required field - missing it raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            del record["repo_commit_sha"]
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("repo_commit_sha", str(ctx.exception))

    def test_issue_title_with_commit_sha_truncated_to_12_chars(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()

            _write_run_record(run_dir, record)
            payload = publish_helpers.build_publication_payload(run_dir)

            # Title should contain the first 12 chars of the commit sha
            self.assertIn("@ abcdef123456", payload["title"])

    def test_run_json_not_an_object_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text("[1, 2, 3]", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("must be a JSON object", str(ctx.exception))

    def test_build_issue_payload_is_alias_for_build_publication_payload(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            _write_run_record(run_dir, _valid_run_record())

            payload1 = publish_helpers.build_publication_payload(run_dir)
            payload2 = publish_helpers.build_issue_payload(run_dir)

            self.assertEqual(payload1, payload2)

    def test_validate_publishable_run_record_is_alias_for_validate_run_record(self):
        record = _valid_run_record()

        result1 = publish_helpers.validate_run_record(record)
        result2 = publish_helpers.validate_publishable_run_record(record)

        self.assertEqual(result1, result2)

    def test_render_issue_body_is_alias_for_render_publication_body(self):
        payload = {"test": "data"}

        result1 = publish_helpers.render_publication_body(payload)
        result2 = publish_helpers.render_issue_body(payload)

        self.assertEqual(result1, result2)

    # === ADVERSARIAL SECURITY TESTS ===

    def test_unicode_null_byte_in_task_raises_or_sanitizes(self):
        """Null bytes in task string should be handled safely."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["task"] = "test\x00task"  # Null byte injection
            _write_run_record(run_dir, record)

            # Either raises an error or handles it safely - should not crash
            try:
                payload = publish_helpers.build_publication_payload(run_dir)
                # If it succeeds, verify task is in output
                self.assertIn("task", payload["run_record"])
            except (ValueError, json.JSONDecodeError):
                pass  # Acceptable - null bytes rejected

    def test_unicode_rtl_override_in_status(self):
        """Right-to-left override characters could obscure status."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            # RTL override character - could make "passed" appear as "sedpass"
            record["status"] = "passed\u202efailed"
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # The RTL override should be preserved or rejected - check slugification
            # produces a safe label
            for label in payload["labels"]:
                self.assertNotIn("\u202e", label)  # Labels should not contain RTL

    def test_unicode_homoglyph_in_commit_sha(self):
        """Lookalike unicode characters in commit SHA (e.g., Cyrillic 'о' vs '0')."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            # Cyrillic 'о' (U+043E) looks like 'o' but is not valid hex
            record["repo_commit_sha"] = "аbcdef1234567890abcdef1234567890abcdef1"
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("repo_commit_sha", str(ctx.exception))

    def test_html_script_tag_in_task(self):
        """Script injection in task field."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["task"] = "<script>alert(1)</script>"
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Task should be stored as-is in run_record
            self.assertEqual(payload["run_record"]["task"], "<script>alert(1)</script>")

    def test_template_literal_injection_in_status(self):
        """Template literal injection in status field."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["status"] = (
                "${process.mainModule.require('child_process').execSync('ls')}"
            )
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Status is stored as-is; the slugification should process it
            # The template literal is slugified into label
            self.assertTrue(
                any("status" in label for label in payload["labels"]),
                f"Expected status label, got {payload['labels']}",
            )

    def test_path_traversal_in_task(self):
        """Path traversal attempts in task field."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["task"] = "../../../etc/passwd"
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Task should be stored as-is
            self.assertEqual(payload["run_record"]["task"], "../../../etc/passwd")

    def test_sql_injection_in_status(self):
        """SQL-like fragments in status field."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["status"] = "passed'; DROP TABLE runs;--"
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Status should be slugified - dangerous chars become hyphens
            self.assertIn("status:error", payload["labels"])

    def test_very_long_task_string(self):
        """Oversized input - very long task string (>10KB)."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["task"] = "a" * 20000  # 20KB string
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Should handle it without crashing
            self.assertEqual(len(payload["run_record"]["task"]), 20000)

    def test_deeply_nested_json_object(self):
        """Deeply nested JSON objects (>100 levels)."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            # Build deeply nested structure
            nested = {"key": "value"}
            for _ in range(150):
                nested = {"nested": nested}
            record = _valid_run_record()
            record["extra_data"] = nested
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Should handle it without crashing
            self.assertIn("extra_data", payload["run_record"])

    def test_null_value_in_optional_field(self):
        """Null repo provenance is accepted and surfaced as a warning."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["repo_branch"] = None
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)

            self.assertIn("track:experimental", payload["labels"])
            self.assertIn("repo_branch_missing", payload["signals"])
            self.assertIn(
                "repository branch could not be resolved at completion time",
                payload["warnings"],
            )

    def test_array_instead_of_string_field(self):
        """Array where string is expected."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["task"] = ["task1", "task2"]  # Should be string
            _write_run_record(run_dir, record)

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("task", str(ctx.exception))

    def test_leading_trailing_whitespace_in_commit_sha(self):
        """Whitespace in commit SHA should be trimmed."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["repo_commit_sha"] = "  abcdef1234567890abcdef1234567890abcdef12  "
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Should be trimmed and lowercased
            self.assertEqual(
                payload["run_record"]["repo_commit_sha"],
                "abcdef1234567890abcdef1234567890abcdef12",
            )

    def test_uppercase_hex_in_commit_sha_is_lowercased(self):
        """Uppercase hex in SHA should be normalized to lowercase."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["repo_commit_sha"] = "ABCDEF1234567890ABCDEF1234567890ABCDEF12"
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Should be normalized to lowercase
            self.assertEqual(
                payload["run_record"]["repo_commit_sha"],
                "abcdef1234567890abcdef1234567890abcdef12",
            )

    def test_payload_determinism_with_special_unicode_in_task(self):
        """Payload should be deterministic even with special unicode chars."""
        with tempfile.TemporaryDirectory() as td:
            run_dir_a = Path(td) / "a"
            run_dir_b = Path(td) / "b"

            record = _valid_run_record()
            record["task"] = "test-\u00e9\u00e8\u00ea"  # Accented chars

            _write_run_record(run_dir_a, record)
            _write_run_record(run_dir_b, record)

            payload_a = publish_helpers.build_publication_payload(run_dir_a)
            payload_b = publish_helpers.build_publication_payload(run_dir_b)

            # Bodies must be identical for same input
            self.assertEqual(payload_a["body"], payload_b["body"])

    def test_nan_score_value(self):
        """NaN in score field should be accepted (numeric)."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["score"] = float("nan")
            _write_run_record(run_dir, record)

            # NaN is technically a float, so it should be accepted
            payload = publish_helpers.build_publication_payload(run_dir)
            import math

            self.assertTrue(math.isnan(payload["run_record"]["score"]))

    def test_infinity_score_value(self):
        """Infinity in score field should be accepted (numeric)."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["score"] = float("inf")
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            self.assertEqual(payload["run_record"]["score"], float("inf"))

    def test_negative_zero_score(self):
        """Negative zero score should be handled."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["score"] = -0.0
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            self.assertEqual(payload["run_record"]["score"], -0.0)

    def test_empty_array_as_root_json(self):
        """Empty array [] as root JSON should fail (not an object)."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text("[]", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("must be a JSON object", str(ctx.exception))

    def test_json_top_level_string(self):
        """JSON root being a string instead of object should fail."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text('"just a string"', encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                publish_helpers.build_publication_payload(run_dir)

            self.assertIn("must be a JSON object", str(ctx.exception))

    def test_emoji_in_status_field(self):
        """Emoji characters in status field."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["status"] = "passed\u2728"  # Sparkles emoji
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Non-canonical status values should fall back to status:error
            self.assertIn("status:error", payload["labels"])

    def test_combining_characters_in_task(self):
        """Combining characters that modify string visually."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            # Combining diaeresis after 'a' - visually looks like 'a' but different
            record["task"] = "test\u0308task"
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Should preserve the combining char
            self.assertIn("\u0308", payload["run_record"]["task"])

    def test_zero_width_space_in_task(self):
        """Zero-width space (invisible character) in task."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["task"] = "test\u200btask"  # Zero-width space
            _write_run_record(run_dir, record)

            payload = publish_helpers.build_publication_payload(run_dir)
            # Zero-width space should be preserved in output
            self.assertIn("\u200b", payload["run_record"]["task"])

    def test_json_with_duplicate_keys(self):
        """JSON with duplicate keys - last value wins in Python json module."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            record = _valid_run_record()
            record["status"] = "first"
            # Write record with duplicate key
            run_dir.mkdir(parents=True, exist_ok=True)
            # Manually write with duplicate
            content = '{"schema_version":"1.0.0","completed_at":"2026-03-28T12:34:56Z","repo_commit_sha":"abcdef1234567890abcdef1234567890abcdef12","repo_branch":"main","repo_dirty":false,"task":"suite/task","status":"failed","score":1.0}'
            (run_dir / "run.json").write_text(content, encoding="utf-8")

            # Wait - the above doesn't test what I wanted. Let me fix.
            run_dir2 = Path(td) / "dup"
            run_dir2.mkdir(parents=True, exist_ok=True)
            # Duplicate status key - Python json uses last value
            dup_content = '{"schema_version":"1.0.0","completed_at":"2026-03-28T12:34:56Z","repo_commit_sha":"abcdef1234567890abcdef1234567890abcdef12","repo_branch":"main","repo_dirty":false,"task":"suite/task","status":"passed","score":1.0,"status":"failed"}'
            (run_dir2 / "run.json").write_text(dup_content, encoding="utf-8")

            payload = publish_helpers.build_publication_payload(run_dir2)
            # Last value "failed" should win
            self.assertEqual(payload["run_record"]["status"], "failed")
