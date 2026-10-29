"""Recorded gate outcomes with real CLI children in disposable projects."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OfflineFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("tools/offline_check.py", "src/adapters/files.py", "src/domain/errors.py"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        # Only the external check programs are fixtures; the recorder and isolation are real.
        self.write("mypy.py", 'print("typecheck output")\n')
        self.write("src/ops.py", 'print("demo output")\n')
        self.write("tools/sql_inventory.py", 'print("inventory output")\n')
        self.write("tests/test_sample.py", "import unittest\nclass Sample(unittest.TestCase):\n    def test_ok(self): self.assertEqual(2, 2)\n")
        self.write("tests/fixtures/input.json", '{}\n')
        self.write("pyproject.toml", '[tool.mypy]\nfiles = ["src/ops.py"]\n')
        self.write("README.md", "Fixture project\n")

    def write(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def command(self, record="record", *, isolate=True):
        command = [sys.executable, str(self.root / "tools/offline_check.py"),
                   "--parent-netns", os.readlink("/proc/self/ns/net"),
                   "--state-dir", str(self.root / "state")]
        if record is not None:
            command.extend(["--record-dir", str(self.root / record)])
        if isolate:
            command = ["unshare", "--user", "--map-root-user", "--net", "--", *command]
        return command

    def run_gate(self, record="record", *, isolate=True):
        child = subprocess.run(self.command(record, isolate=isolate), cwd=self.root,
                               capture_output=True, text=True, timeout=20)
        result = json.loads((self.root / record / "result.json").read_text(encoding="utf-8"))
        return child, result


class OfflineRecordingTests(OfflineFixture):
    def test_success_records_conditions_commands_and_logs_without_private_inputs(self):
        self.write(".env", "SECRET=synthetic-private-value\n")
        self.write("data/private.json", '{"private": "synthetic-private-value"}\n')
        child, result = self.run_gate()
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["conditions_unchanged"])
        self.assertEqual([step["name"] for step in result["steps"]],
                         ["namespace", "typecheck", "unittest", "demo", "sql-inventory"])
        for step in result["steps"]:
            self.assertEqual((step["status"], step["exit_code"]), ("PASS", 0))
            self.assertGreaterEqual(step["elapsed_seconds"], 0)
            self.assertTrue((self.root / "record" / step["log"]).read_text(encoding="utf-8"))
        self.assertEqual(result["steps"][1]["command"],
                         [sys.executable, "-m", "mypy", "--config-file", "pyproject.toml"])
        self.assertEqual(result["conditions"]["files"]["tests/fixtures/input.json"],
                         hashlib.sha256(b'{}\n').hexdigest())
        self.assertIn("sqlite", result["conditions"]["environment"])
        self.assertIn("packages", result["conditions"]["environment"])
        self.assertNotIn(".env", result["conditions"]["files"])
        self.assertNotIn("synthetic-private-value", json.dumps(result))

    def test_failed_check_keeps_exit_code_log_and_remaining_not_run(self):
        self.write("mypy.py", 'print("intentional check failure")\nraise SystemExit(7)\n')
        child, result = self.run_gate()
        self.assertEqual(child.returncode, 1)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["steps"][1]["exit_code"], 7)
        self.assertIn("intentional check failure", (self.root / "record/01-typecheck.log").read_text(encoding="utf-8"))
        self.assertTrue(all(step["status"] == "NOT_RUN" for step in result["steps"][2:]))

    def test_later_failure_does_not_relabel_prior_success(self):
        self.write("tests/test_sample.py", "import unittest\nclass Sample(unittest.TestCase):\n    def test_bad(self): self.fail('intentional test failure')\n")
        child, result = self.run_gate()
        self.assertEqual(child.returncode, 1)
        self.assertEqual([step["status"] for step in result["steps"]],
                         ["PASS", "PASS", "FAIL", "NOT_RUN", "NOT_RUN"])

    def test_isolation_failure_is_recorded_before_any_checks(self):
        child, result = self.run_gate(isolate=False)
        self.assertEqual(child.returncode, 1)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["steps"][0]["error"], "NETWORK_NAMESPACE_NOT_ISOLATED")
        self.assertTrue(all(step["status"] == "NOT_RUN" for step in result["steps"][1:]))

    def test_existing_result_directory_is_never_overwritten(self):
        child, _ = self.run_gate()
        self.assertEqual(child.returncode, 0, child.stderr)
        before = {p.name: p.read_bytes() for p in (self.root / "record").iterdir()}
        child, _ = self.run_gate()
        self.assertNotEqual(child.returncode, 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.root / "record").iterdir()})

    def test_test_config_and_environment_changes_have_distinct_conditions(self):
        _, previous = self.run_gate("baseline")
        for record, name, body in (
            ("test-change", "tests/fixtures/input.json", '{"changed": true}\n'),
            ("config-change", "pyproject.toml", '[tool.mypy]\nfiles = ["src/ops.py"]\ncheck_untyped_defs = true\n'),
            ("environment-change", "validation_fixture-1.0.dist-info/METADATA", "Name: validation-fixture\nVersion: 1.0\n"),
        ):
            with self.subTest(record=record):
                self.write(name, body)
                child, current = self.run_gate(record)
                self.assertEqual(child.returncode, 0, child.stderr)
                self.assertNotEqual(previous["conditions_sha256"], current["conditions_sha256"])
                previous = current
        self.assertEqual(previous["conditions"]["environment"]["packages"]["validation-fixture"], "1.0")

    def test_input_change_during_checks_prevents_overall_pass(self):
        self.write("mypy.py", "from pathlib import Path\nPath('src/ops.py').write_text('print(42)\\n')\n")
        child, result = self.run_gate()
        self.assertEqual(child.returncode, 1)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(all(step["status"] == "PASS" for step in result["steps"]))
        self.assertFalse(result["conditions_unchanged"])
        self.assertNotEqual(result["conditions_sha256"], result["final_conditions_sha256"])

    def test_sigterm_records_interruption_and_stops_child_group(self):
        self.write("mypy.py", "import subprocess, sys, time\nfrom pathlib import Path\nchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\nprint('before interruption', flush=True)\nPath('child.pid').write_text(str(child.pid))\ntime.sleep(60)\n")
        with subprocess.Popen(self.command(), cwd=self.root, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, start_new_session=True) as child:
            try:
                deadline = time.monotonic() + 10
                while not (self.root / "child.pid").exists() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue((self.root / "child.pid").exists())
                child.send_signal(signal.SIGTERM)
                stdout, stderr = child.communicate(timeout=10)
                self.assertEqual(child.returncode, 143, stdout + stderr)
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
        result = json.loads((self.root / "record/result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "INTERRUPTED")
        self.assertEqual(result["steps"][1]["status"], "INTERRUPTED")
        self.assertTrue(all(step["status"] == "NOT_RUN" for step in result["steps"][2:]))
        self.assertIn("before interruption", (self.root / "record/01-typecheck.log").read_text(encoding="utf-8"))
        pid = int((self.root / "child.pid").read_text(encoding="utf-8"))
        status = Path(f"/proc/{pid}/stat")
        self.assertTrue(not status.exists() or status.read_text(encoding="utf-8").split()[2] == "Z")

    def test_legacy_call_keeps_the_existing_three_checks(self):
        self.write("mypy.py", 'raise AssertionError("legacy mode must not add typecheck")\n')
        child = subprocess.run(self.command(record=None), cwd=self.root,
                               capture_output=True, text=True, timeout=20)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertIn("demo output", child.stdout)
        self.assertIn("inventory output", child.stdout)
        self.assertFalse((self.root / "record").exists())


if __name__ == "__main__":
    unittest.main()
