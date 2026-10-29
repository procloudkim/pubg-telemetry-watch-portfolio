"""Validation evidence is interpreted through its public CLI and real files."""

import json
import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from test_offline_check import OfflineFixture


class ValidationStatusTests(OfflineFixture):
    def setUp(self):
        super().setUp()
        shutil.copyfile(Path(__file__).resolve().parents[1] / "tools/validation_status.py",
                        self.root / "tools/validation_status.py")

    def read_status(self):
        child = subprocess.run(
            [sys.executable, str(self.root / "tools/validation_status.py"),
             str(self.root / "record/result.json")], cwd=self.root,
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertTrue(child.stdout.strip(), child.stderr)
        return child, json.loads(child.stdout)

    def test_completed_record_reports_current_pass_without_changing_evidence(self):
        gate, _ = self.run_gate()
        self.assertEqual(gate.returncode, 0, gate.stderr)
        before = {p.name: p.read_bytes() for p in (self.root / "record").iterdir()}
        child, summary = self.read_status()
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(summary["recorded_status"], "PASS")
        self.assertTrue(summary["current_pass"])
        self.assertTrue(summary["conditions_match"])
        self.assertEqual([step["name"] for step in summary["steps"]],
                         ["namespace", "typecheck", "unittest", "demo", "sql-inventory"])
        self.assertEqual(summary["steps"][1]["command"],
                         [sys.executable, "-m", "mypy", "--config-file", "pyproject.toml"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.root / "record").iterdir()})

    def test_malformed_or_unsupported_records_are_rejected(self):
        gate, original = self.run_gate()
        self.assertEqual(gate.returncode, 0, gate.stderr)
        bodies = ['{"status":', '[]', '{}', '{"schema_version":1,"schema_version":2}']
        for key, value in (
            ("schema_version", 2), ("schema_version", True), ("status", "UNKNOWN"),
            ("exit_code", False), ("finished_at", None), ("conditions_sha256", "0" * 64),
            ("steps", []), ("steps", original["steps"][:-1]),
            ("cwd", None), ("invocation", []), ("namespace", None),
            ("namespace", {"parent": original["namespace"]["parent"],
                           "current": original["namespace"]["parent"]}),
        ):
            bodies.append(json.dumps({**original, key: value}))
        for key, value in (("exit_code", False), ("exit_code", 9), ("command", []),
                           ("elapsed_seconds", float("nan")), ("scope", None),
                           ("log", "../private-marker")):
            changed = copy.deepcopy(original)
            changed["steps"][1][key] = value
            bodies.append(json.dumps(changed))
        for body in bodies:
            with self.subTest(body=body[:60]):
                self.write("record/result.json", body)
                child, summary = self.read_status()
                self.assertEqual(child.returncode, 2, child.stderr)
                self.assertFalse(summary["record_valid"])
                self.assertFalse(summary["current_pass"])
                self.assertTrue(summary["issues"])

    def test_current_file_and_environment_changes_preserve_the_historical_pass(self):
        gate, _ = self.run_gate()
        self.assertEqual(gate.returncode, 0, gate.stderr)
        original = (self.root / "record/result.json").read_bytes()
        for name, body, kind, key in (
            ("tests/fixtures/input.json", '{"changed":true}\n', "files", "tests/fixtures/input.json"),
            ("pyproject.toml", '[tool.mypy]\nfiles=["src/ops.py"]\ncheck_untyped_defs=true\n', "files", "pyproject.toml"),
            ("tools/new_check.py", 'print("new")\n', "files", "tools/new_check.py"),
            ("changed_environment-1.0.dist-info/METADATA", "Name: changed-environment\nVersion: 1.0\n", "environment", "packages"),
        ):
            with self.subTest(name=name):
                self.write(name, body)
                child, summary = self.read_status()
                self.assertEqual(child.returncode, 1, child.stderr)
                self.assertTrue(summary["record_valid"])
                self.assertEqual(summary["recorded_status"], "PASS")
                self.assertFalse(summary["current_pass"])
                self.assertFalse(summary["conditions_match"])
                self.assertIn(key, summary["differences"][kind])
                self.assertEqual((self.root / "record/result.json").read_bytes(), original)

    def test_missing_or_unsafe_logs_prevent_current_pass_without_reading_their_content(self):
        gate, _ = self.run_gate()
        self.assertEqual(gate.returncode, 0, gate.stderr)
        log = self.root / "record/01-typecheck.log"
        log.unlink()
        self.write("private-marker", "PRIVATE_CONTENT_MUST_NOT_APPEAR")
        for kind in ("missing", "symlink", "fifo"):
            with self.subTest(kind=kind):
                if kind == "symlink":
                    log.symlink_to(self.root / "private-marker")
                elif kind == "fifo":
                    log.unlink()
                    os.mkfifo(log)
                child, summary = self.read_status()
                self.assertEqual(child.returncode, 1, child.stderr)
                self.assertEqual(summary["recorded_status"], "PASS")
                self.assertFalse(summary["current_pass"])
                self.assertFalse(summary["steps"][1]["log_available"])
                self.assertIn("LOG_UNAVAILABLE:typecheck", summary["issues"])
                self.assertNotIn("PRIVATE_CONTENT_MUST_NOT_APPEAR", child.stdout)

    def test_failed_step_and_unrun_steps_remain_distinct(self):
        self.write("mypy.py", "raise SystemExit(7)\n")
        gate, _ = self.run_gate()
        self.assertEqual(gate.returncode, 1, gate.stderr)
        child, summary = self.read_status()
        self.assertEqual(child.returncode, 1, child.stderr)
        self.assertTrue(summary["record_valid"])
        self.assertEqual(summary["recorded_status"], "FAIL")
        self.assertEqual([step["status"] for step in summary["steps"]],
                         ["PASS", "FAIL", "NOT_RUN", "NOT_RUN", "NOT_RUN"])
        self.assertEqual(summary["steps"][1]["exit_code"], 7)
        self.assertFalse(summary["current_pass"])
        self.assertEqual(summary["issues"], [])
        self.assertIn("typecheck", summary["next_action"])

    def test_running_checkpoint_does_not_assume_the_process_is_dead(self):
        gate, original = self.run_gate()
        self.assertEqual(gate.returncode, 0, gate.stderr)
        record = copy.deepcopy(original)
        record.update(status="RUNNING", exit_code=None)
        for key in ("finished_at", "final_conditions_sha256", "conditions_unchanged"):
            record.pop(key)
        for index, step in enumerate(record["steps"][1:], 1):
            step.update(status="RUNNING" if index == 1 else "NOT_RUN",
                        exit_code=None, elapsed_seconds=None)
            (self.root / "record" / step["log"]).unlink()
        self.write("record/result.json", json.dumps(record))
        child, summary = self.read_status()
        self.assertEqual(child.returncode, 1, child.stderr)
        self.assertTrue(summary["record_valid"])
        self.assertEqual(summary["recorded_status"], "RUNNING")
        self.assertFalse(summary["current_pass"])
        self.assertEqual(summary["issues"], [])
        self.assertIn("still running", summary["next_action"])

    def test_interrupted_record_and_log_language_do_not_become_a_pass(self):
        gate, record = self.run_gate()
        self.assertEqual(gate.returncode, 0, gate.stderr)
        record.update(status="INTERRUPTED", exit_code=130)
        record["steps"][-1].update(status="INTERRUPTED", exit_code=-15)
        marker = self.root / "executed-command"
        record["steps"][-1]["command"] = [sys.executable, "-c",
            f"from pathlib import Path; Path({str(marker)!r}).write_text('wrong')"]
        self.write("record/result.json", json.dumps(record))
        for log in (self.root / "record").glob("*.log"):
            log.write_bytes(b"PASS\n\xff\xfe\n")
        before = {p.name: p.read_bytes() for p in (self.root / "record").iterdir()}
        child, summary = self.read_status()
        self.assertEqual(child.returncode, 1, child.stderr)
        self.assertTrue(summary["record_valid"])
        self.assertEqual(summary["recorded_status"], "INTERRUPTED")
        self.assertFalse(summary["current_pass"])
        self.assertIn("interrupted", summary["next_action"])
        self.assertFalse(marker.exists())
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.root / "record").iterdir()})

    def test_unavailable_current_environment_preserves_valid_historical_status(self):
        gate, _ = self.run_gate()
        self.assertEqual(gate.returncode, 0, gate.stderr)
        self.write("broken_environment-1.0.dist-info/METADATA", "Version: 1.0\n")
        child, summary = self.read_status()
        self.assertEqual(child.returncode, 2, child.stderr)
        self.assertTrue(summary["record_valid"])
        self.assertEqual(summary["recorded_status"], "PASS")
        self.assertIsNone(summary["conditions_match"])
        self.assertFalse(summary["current_pass"])
        self.assertIn("CURRENT_CONDITIONS_UNAVAILABLE", summary["issues"])

    def test_unreadable_input_returns_json_error_without_blocking_on_a_fifo(self):
        path = self.root / "record/result.json"
        path.parent.mkdir()
        for kind in ("missing", "invalid_utf8", "fifo", "symlink_loop"):
            with self.subTest(kind=kind):
                if kind == "invalid_utf8":
                    path.write_bytes(b"\xff\xfe")
                elif kind == "fifo":
                    os.mkfifo(path)
                elif kind == "symlink_loop":
                    path.symlink_to(path)
                try:
                    child, summary = self.read_status()
                    self.assertEqual(child.returncode, 2, child.stderr)
                    self.assertFalse(summary["record_valid"])
                    self.assertFalse(summary["current_pass"])
                    self.assertNotIn("Traceback", child.stderr)
                finally:
                    path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
