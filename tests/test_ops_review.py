from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src import ops
from src.adapters import sqlite_ops
from src.common import ROOT, sha256_file
from src.ops_demo import write_inputs


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state, self.inputs = self.root / "state", self.root / "inputs"
        self.fixture = json.loads((ROOT / "tests/fixtures/TESTMATCH.telemetry.json").read_text())
        self.manifest = write_inputs(self.inputs, [("TESTMATCH", self.fixture)])

    def tearDown(self):
        self.temporary.cleanup()

    def run_batch(self, name="batch", manifest=None):
        return ops.run_batch(
            name, manifest or self.manifest, state_dir=self.state, source_root=self.inputs
        )

    def cli(self, *arguments, expected=0):
        child = subprocess.run(
            [sys.executable, "-m", "src.ops", "review", *arguments, "--state-dir", str(self.state)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(child.returncode, expected, child.stderr + child.stdout)
        self.assertNotIn("Traceback", child.stderr)
        return json.loads(child.stdout)

    def case(self):
        return ops.review_list(state_dir=self.state)["cases"][0]["case_id"]

    def test_cli_transitions_filters_evidence_notes_and_replay(self):
        first = self.run_batch()
        cases = self.cli("list", "--batch-id", "batch", "--state", "OPEN")["cases"]
        self.assertEqual(len(cases), 2)
        case = cases[0]["case_id"]
        shown = self.cli("show", "--case-id", case)
        self.assertEqual(shown["signal"]["player"], "pla***")
        self.assertTrue(shown["signal"]["evidence"])
        self.assertEqual(shown["history"][0]["action"], "created")
        for action, expected in [
            ("start", "IN_REVIEW"),
            ("note", "IN_REVIEW"),
            ("complete", "COMPLETED"),
        ]:
            extra = ["--note", "synthetic evidence checked"] if action == "note" else []
            changed = self.cli(action, "--case-id", case, "--operator", "operator-1", *extra)
            self.assertEqual(changed["state"], expected)
        before = self.cli("show", "--case-id", case)
        for batch in ("batch", "other"):
            self.assertEqual(self.run_batch(batch)["attempts"], first["attempts"])
            ops.report_batch(batch, state_dir=self.state)
        self.assertEqual(before, self.cli("show", "--case-id", case))
        self.assertEqual(
            len(self.cli("list", "--batch-id", "other", "--state", "COMPLETED")["cases"]), 1
        )
        self.assertEqual(len(self.cli("list")["cases"]), 2)
        self.assertEqual(
            self.cli("reopen", "--case-id", case, "--operator", "operator-2")["state"], "OPEN"
        )
        history = self.cli("show", "--case-id", case)["history"]
        self.assertEqual(
            [r["action"] for r in history], ["created", "start", "note", "complete", "reopen"]
        )
        self.assertEqual(history[2]["note"], "synthetic evidence checked")
        self.assertEqual(history[-1]["operator"], "operator-2")

    def test_invalid_inputs_missing_rows_and_writer_conflict_leave_history_unchanged(self):
        self.run_batch()
        case = self.case()
        before = ops.review_show(case, state_dir=self.state)
        cases = [
            (["complete", "--operator", "one"], "REVIEW_INVALID_TRANSITION"),
            (["reopen", "--operator", "one"], "REVIEW_INVALID_TRANSITION"),
            (["start", "--operator", "  "], "REVIEW_OPERATOR_REQUIRED"),
            (["note", "--operator", "one", "--note", "\n "], "REVIEW_NOTE_REQUIRED"),
        ]
        for arguments, code in cases:
            self.assertEqual(self.cli(*arguments, "--case-id", case, expected=2), {"error": code})
        self.assertEqual(
            self.cli("show", "--case-id", "missing", expected=2), {"error": "REVIEW_CASE_NOT_FOUND"}
        )
        self.assertEqual(
            self.cli("list", "--batch-id", "missing", expected=2), {"error": "BATCH_NOT_FOUND"}
        )
        with ops.writer_lock(self.state):
            self.assertEqual(
                self.cli("start", "--case-id", case, "--operator", "one", expected=2),
                {"error": "WORKER_BUSY"},
            )
        self.assertEqual(before, ops.review_show(case, state_dir=self.state))

    def test_retry_of_another_failed_job_preserves_completed_case_and_notes(self):
        manifest = write_inputs(
            self.root / "mixed", [("BROKEN", self.fixture), ("GOOD", self.fixture)]
        )
        with ops.writer_lock(self.state), closing(ops.connect(self.state)) as connection:
            ops.register(connection, "mixed", manifest, self.root / "mixed")
        source = self.root / "mixed/telemetry/BROKEN.json"
        original = source.read_bytes()
        source.write_bytes(b"{")
        result = ops.run_batch("mixed", state_dir=self.state)
        self.assertEqual(result["counts"]["FAILED"], 1)
        case = self.case()
        for action in ("start", "note", "complete"):
            ops.review_change(
                action,
                case,
                "operator",
                note="retain this" if action == "note" else None,
                state_dir=self.state,
            )
        before = ops.review_show(case, state_dir=self.state)
        source.write_bytes(original)
        failed = next(j["job_id"] for j in result["jobs"] if j["state"] == "FAILED")
        ops.retry_job("mixed", failed, state_dir=self.state)
        self.assertTrue(ops.run_batch("mixed", state_dir=self.state)["complete"])
        ops.report_batch("mixed", state_dir=self.state)
        self.assertEqual(before, ops.review_show(case, state_dir=self.state))
        self.assertEqual(len(ops.review_list(state_dir=self.state)["cases"]), 4)

    def test_case_constraints_and_append_only_history(self):
        self.run_batch()
        with closing(ops.connect(self.state)) as connection:
            case = connection.execute("SELECT * FROM review_case LIMIT 1").fetchone()
            with self.assertRaises(sqlite3.IntegrityError), connection:
                connection.execute(
                    "INSERT INTO review_case VALUES (?,?,?,?,?,?,?)",
                    ("different", *tuple(case)[1:]),
                )
            for query in (
                "UPDATE review_history SET operator='changed'",
                "DELETE FROM review_history",
            ):
                with self.assertRaisesRegex(sqlite3.IntegrityError, "APPEND_ONLY"), connection:
                    connection.execute(query)
            with self.assertRaises(sqlite3.IntegrityError), connection:
                connection.execute(
                    "INSERT INTO review_history VALUES (?,?,?,?,?,?,?,?)",
                    (
                        case["case_id"],
                        2,
                        "start",
                        "operator",
                        ops.utc_now(),
                        None,
                        "IN_REVIEW",
                        None,
                    ),
                )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM review_history").fetchone()[0], 2
            )

    def test_old_schema_is_rejected_without_modification(self):
        self.state.mkdir()
        path = self.state / "ops.sqlite3"
        with closing(sqlite3.connect(path)) as connection:
            connection.executescript("CREATE TABLE legacy (n INTEGER); PRAGMA user_version=1;")
        before = sha256_file(path)
        for readonly in (False, True):
            with self.assertRaisesRegex(ops.OpsError, "UNSUPPORTED_DATABASE_SCHEMA"):
                ops.connect(self.state, readonly=readonly)
            self.assertEqual(sha256_file(path), before)

    def test_process_exit_keeps_review_state_and_history_atomic(self):
        script = """
import os,sys,sqlite3
from pathlib import Path
from unittest.mock import patch
from src import ops
from src.adapters import sqlite_ops, batch_inputs, files
from src.adapters.environment import Environment
state,case,action,phase=Path(sys.argv[1]),*sys.argv[2:]
class Connection(sqlite3.Connection):
    def execute(self,sql,*args):
        result=super().execute(sql,*args)
        if phase=='after_state' and sql.startswith('UPDATE review_case'):
            os._exit(37)
        return result
    def commit(self):
        if phase=='before_commit': os._exit(37)
        super().commit()
        if phase=='after_commit': os._exit(37)
original=sqlite3.connect
def connect(*args,**kwargs): return original(*args,**kwargs,factory=Connection)
with patch.object(sqlite_ops.sqlite3,'connect',side_effect=connect):
    ops.review_change(action,case,'crash-test',note='durable note' if action=='note' else None,state_dir=state)
"""
        for action in ("start", "note"):
            for phase in ("after_state", "before_commit", "after_commit"):
                with self.subTest(action=action, phase=phase):
                    self.state = self.root / (action + "-" + phase)
                    self.run_batch()
                    case = self.case()
                    before = ops.review_show(case, state_dir=self.state)
                    child = subprocess.run(
                        [sys.executable, "-c", script, str(self.state), case, action, phase],
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                    self.assertEqual(child.returncode, 37, child.stderr)
                    after = ops.review_show(case, state_dir=self.state)
                    if phase == "after_commit":
                        self.assertEqual(len(after["history"]), 2)
                        self.assertEqual(after["history"][-1]["action"], action)
                        self.assertEqual(
                            after["case"]["state"], "IN_REVIEW" if action == "start" else "OPEN"
                        )
                        self.assertEqual(
                            after["history"][-1]["note"],
                            "durable note" if action == "note" else None,
                        )
                    else:
                        self.assertEqual(before, after)

    def test_timing_write_failure_does_not_revert_committed_results(self):
        original = sqlite3.connect

        class Connection(sqlite3.Connection):
            def execute(self, sql, *args):
                if sql.startswith("UPDATE attempt SET stage_seconds_json="):
                    raise sqlite3.OperationalError("timing write failed")
                return super().execute(sql, *args)

        with patch.object(
            sqlite_ops.sqlite3,
            "connect",
            side_effect=lambda *a, **k: original(*a, **k, factory=Connection),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                self.run_batch()
        result = ops.run_batch("batch", state_dir=self.state)
        self.assertTrue(result["complete"])
        self.assertEqual(result["metrics"]["attempts"], 1)
        self.assertEqual(result["metrics"]["successful_duration_samples"], 0)
        self.assertIsNone(result["metrics"]["events_per_measured_second"])
        self.assertEqual(len(ops.review_list(state_dir=self.state)["cases"]), 2)

    def test_sqlite_backup_restores_history_integrity_and_report_bytes(self):
        self.run_batch()
        case = self.case()
        for action in ("start", "note", "complete"):
            ops.review_change(
                action,
                case,
                "backup-test",
                note="persist me" if action == "note" else None,
                state_dir=self.state,
            )
        ops.report_batch("batch", state_dir=self.state)
        restored = self.root / "restored"
        restored.mkdir()
        with ops.writer_lock(self.state), closing(ops.connect(self.state, readonly=True)) as source:
            with closing(sqlite3.connect(restored / "ops.sqlite3")) as target:
                source.backup(target)
                self.assertEqual(target.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(target.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(list(source.iterdump()), list(target.iterdump()))
        self.assertEqual(
            ops.review_show(case, state_dir=self.state), ops.review_show(case, state_dir=restored)
        )
        ops.report_batch("batch", state_dir=restored)
        for path in (self.state / "reports/batch").iterdir():
            self.assertEqual(
                path.read_bytes(), (restored / "reports/batch" / path.name).read_bytes()
            )


if __name__ == "__main__":
    unittest.main()
