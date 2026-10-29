import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

from src import ops
from src.adapters import sqlite_ops, batch_inputs, files
from src.adapters.environment import Environment
from src.common import ROOT, sha256_file
from src.ops_demo import demo, r2_fixture, write_inputs


class OperationsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.inputs, self.state = self.root / "inputs", self.root / "state"
        self.fixture = json.loads(
            (ROOT / "tests/fixtures/TESTMATCH.telemetry.json").read_text(encoding="utf-8")
        )

    def tearDown(self):
        self.temporary.cleanup()

    def prepare(self, matches=None, **kwargs):
        return write_inputs(self.inputs, matches or [("TESTMATCH", self.fixture)], **kwargs)

    def register(self, manifest):
        with ops.writer_lock(self.state), closing(ops.connect(self.state)) as connection:
            ops.register(connection, "batch", manifest, self.inputs)

    def read(self, query):
        with closing(ops.connect(self.state, readonly=True)) as connection:
            return [dict(row) for row in connection.execute(query)]

    def test_demo_runs_the_real_cli_pipeline_without_network_and_reuses_results(self):
        with patch("requests.get", side_effect=AssertionError("network")):
            first, second = demo(self.state), demo(self.state)
        self.assertEqual(first, second)
        self.assertEqual(first["review_signals"], 3)
        self.assertEqual(first["metrics"]["attempts"], 2)
        counts = self.read("SELECT rule,COUNT(*) AS n FROM review_signal GROUP BY rule")
        self.assertEqual(
            {row["rule"]: row["n"] for row in counts},
            {"R1_speed": 1, "R2_hit_ratio": 1, "R3_kill_burst": 1},
        )
        with closing(ops.connect(self.state, readonly=True)) as connection:
            dump = "\n".join(connection.iterdump())
        report = Path(first["report_dir"]) / "review-queue.md"
        text = report.read_text(encoding="utf-8")
        for name in ("normal_A", "fast_B", "driver_C", "burst_D", "synthetic_0", "synthetic-id-0"):
            self.assertNotIn(name, dump)
            self.assertNotIn(name, text)
        before = report.read_bytes()
        ops.report_batch(first["batch_id"], state_dir=self.state)
        self.assertEqual(before, report.read_bytes())

    def test_repeated_registration_across_batches_has_one_committed_result(self):
        manifest = self.prepare()
        first = ops.run_batch("batch", manifest, state_dir=self.state, source_root=self.inputs)
        second = ops.run_batch("other", manifest, state_dir=self.state, source_root=self.inputs)
        self.assertEqual(first["jobs"], second["jobs"])
        self.assertEqual(self.read("SELECT COUNT(*) AS n FROM job")[0]["n"], 1)
        self.assertEqual(self.read("SELECT COUNT(*) AS n FROM attempt")[0]["n"], 1)
        with patch.object(
            Environment, "runtime", return_value={**ops.runtime(), "python": "different"}
        ):
            with self.assertRaisesRegex(ops.OpsError, "BATCH_RUNTIME_CHANGED"):
                ops.run_batch("batch", state_dir=self.state)
        body = json.loads(manifest.read_text())
        body["protocol_version"] = "v1-rules-1"
        manifest.write_text(json.dumps(body), encoding="utf-8")
        with self.assertRaisesRegex(ops.OpsError, "BATCH_INPUT_OR_CODE_CHANGED"):
            ops.run_batch("batch", manifest, state_dir=self.state, source_root=self.inputs)

    def test_demo_registers_a_new_batch_after_runtime_change(self):
        first = demo(self.state)
        with patch("platform.python_version", return_value="3.11.999"):
            second = demo(self.state)
            self.assertEqual(second, demo(self.state))
        self.assertNotEqual(first["batch_id"], second["batch_id"])
        self.assertEqual(second["metrics"]["attempts"], 2)

    def test_replacement_between_validation_and_consumption_is_rejected(self):
        manifest = self.prepare()
        self.register(manifest)
        original = batch_inputs.load_events_path

        def replaced(path, **kwargs):
            path.write_text(json.dumps([{"_T": "Unused"} for _ in self.fixture]), encoding="utf-8")
            return original(path, **kwargs)

        with patch.object(batch_inputs, "load_events_path", side_effect=replaced):
            result = ops.run_batch("batch", state_dir=self.state)
        self.assertEqual(result["counts"]["FAILED"], 1)
        self.assertEqual(result["attempts"][0]["error_code"], "INPUT_CHECKSUM")
        self.assertEqual(self.read("SELECT COUNT(*) AS n FROM player_match")[0]["n"], 0)
        original_read = batch_inputs.read_checked_bytes

        def replaced_metadata(path, expected_sha256):
            path.write_text("[]", encoding="utf-8")
            return original_read(path, expected_sha256)

        with patch.object(batch_inputs, "read_checked_bytes", side_effect=replaced_metadata):
            with self.assertRaisesRegex(ops.OpsError, "INPUT_CHECKSUM"):
                ops.read_inputs(manifest, self.inputs)

    def test_invalid_manifest_and_token_have_json_error_and_exit_2(self):
        manifest = self.prepare()
        source = json.loads(manifest.read_text())
        metadata = self.inputs / "matches/TESTMATCH.json"
        metadata.parent.mkdir()
        metadata.write_text('{"data":null}', encoding="utf-8")
        invalid_metadata = {
            **source,
            "artifacts": source["artifacts"]
            + [
                {
                    "layer": "bronze",
                    "dataset": "matches",
                    "path": "matches/TESTMATCH.json",
                    "sha256": sha256_file(metadata),
                    "bytes": metadata.stat().st_size,
                }
            ],
        }
        for payload, batch, code in [
            ({**source, "quality": None}, "batch", "INPUT_DQ_NOT_PASS"),
            (invalid_metadata, "batch", "INPUT_MATCH_METADATA"),
            (source, "../bad", "INPUT_TOKEN"),
        ]:
            with self.subTest(code=code):
                manifest.write_text(json.dumps(payload), encoding="utf-8")
                child = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "src.ops",
                        "run",
                        "--batch-id",
                        batch,
                        "--manifest",
                        str(manifest),
                        "--source-root",
                        str(self.inputs),
                        "--state-dir",
                        str(self.state),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(child.returncode, 2, child.stderr)
                self.assertEqual(json.loads(child.stdout), {"error": code})
                self.assertNotIn("Traceback", child.stderr)

    def test_sql_compares_raw_event_counts_at_pool_and_attack_boundaries(self):
        matches = [(f"POOL{pool}", r2_fixture(pool)) for pool in (7, 8, 10, 11)]
        matches += [
            (
                "ZERO",
                [
                    {
                        "_T": "LogPlayerTakeDamage",
                        "damage": 1,
                        "attackId": None,
                        "attacker": {"name": "synthetic_zero"},
                    }
                ],
            )
        ]
        for count in (29, 30):
            matches.append(
                (
                    f"ATTACK{count}",
                    [
                        {
                            "_T": "LogPlayerAttack",
                            "attackId": i,
                            "attacker": {"name": "synthetic_low"},
                        }
                        for i in range(count)
                    ],
                )
            )
        for protocol in ("v1-rules-event-context-2", "v1-rules-1"):
            with self.subTest(protocol=protocol):
                root = self.root / protocol
                manifest = write_inputs(root, matches, protocol=protocol)
                result = ops.run_batch(protocol, manifest, state_dir=self.state, source_root=root)
                self.assertTrue(result["complete"], result["attempts"])
        rows = self.read(
            """SELECT j.match_id,j.rule_protocol,p.* FROM player_match p JOIN job j USING(job_id)"""
        )
        for row in rows:
            mid = row["match_id"]
            expected = {
                "POOL7": "match_pool_below_8",
                "POOL8": "match_pool_below_signal_capable",
                "POOL10": "match_pool_below_signal_capable",
                "POOL11": "evaluated",
                "ZERO": "target_below_min_attacks",
                "ATTACK29": "target_below_min_attacks",
                "ATTACK30": "match_pool_below_8",
            }[mid]
            self.assertEqual(row["status"], expected)
            if mid == "POOL11" and row["attacks"] == 31:
                self.assertEqual(
                    row["damage_events"],
                    93 if row["rule_protocol"] == "rules-event-count-1" else 90,
                )
                self.assertEqual(row["review_candidate"], 1)

    def test_constant_pool_has_zero_z_and_no_candidate(self):
        events = r2_fixture()
        events = [row for row in events if row["_T"] == "LogPlayerAttack"]
        result = ops.run_batch(
            "batch",
            self.prepare([("CONST", events)]),
            state_dir=self.state,
            source_root=self.inputs,
        )
        self.assertTrue(result["complete"], result["attempts"])
        self.assertEqual(
            {
                (r["local_z"], r["match_sd"], r["review_candidate"])
                for r in self.read("SELECT * FROM player_match")
            },
            {(0, 1e-9, 0)},
        )

    def test_bad_source_is_isolated_and_retry_requires_explicit_request(self):
        manifest = self.prepare([("BROKEN", self.fixture), ("GOOD", self.fixture)])
        self.register(manifest)
        path = self.inputs / "telemetry/BROKEN.json"
        original = path.read_bytes()
        path.write_bytes(b"{")
        result = ops.run_batch("batch", state_dir=self.state)
        self.assertEqual(result["counts"]["FAILED"], 1)
        self.assertEqual(result["counts"]["SUCCEEDED"], 1)
        ops.report_batch("batch", state_dir=self.state)
        self.assertFalse((self.state / "reports/batch/manifest.json").exists())
        self.assertFalse((self.state / "reports/batch/review-queue.md").exists())
        path.write_bytes(original)
        unchanged = ops.run_batch("batch", state_dir=self.state)
        self.assertEqual(unchanged["attempts"], result["attempts"])
        failed = next(job for job in result["jobs"] if job["state"] == "FAILED")
        ops.retry_job("batch", failed["job_id"], state_dir=self.state)
        recovered = ops.run_batch("batch", state_dir=self.state)
        self.assertTrue(recovered["complete"])
        self.assertEqual(recovered["metrics"]["attempts"], 3)
        ops.report_batch("batch", state_dir=self.state)
        self.assertTrue((self.state / "reports/batch/manifest.json").exists())

    def test_hash_valid_but_broken_json_gzip_and_sql_mismatch_do_not_publish(self):
        for body in (b"{", b"\x1f\x8btruncated", b"{}"):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = write_inputs(root, [("BROKEN", self.fixture)])
                path = root / "telemetry/BROKEN.json"
                path.write_bytes(body)
                value = json.loads(manifest.read_text())
                value["artifacts"][0].update(sha256=sha256_file(path), bytes=len(body))
                manifest.write_text(json.dumps(value), encoding="utf-8")
                result = ops.run_batch(
                    "bad-" + sha256_file(path)[:8], manifest, state_dir=self.state, source_root=root
                )
                self.assertEqual(result["counts"]["FAILED"], 1)
        manifest = self.prepare()
        original = sqlite_ops.sql_measures

        def mismatch(*args):
            rows = original(*args)
            rows[0]["attacks"] += 1
            return rows

        with patch.object(sqlite_ops, "sql_measures", side_effect=mismatch):
            result = ops.run_batch(
                "mismatch", manifest, state_dir=self.state, source_root=self.inputs
            )
        self.assertEqual(result["counts"]["FAILED"], 1)
        self.assertEqual(self.read("SELECT COUNT(*) AS n FROM combat_event")[0]["n"], 0)
        self.assertEqual(self.read("SELECT COUNT(*) AS n FROM review_signal")[0]["n"], 0)

    def test_worker_lock_and_source_path_escape_fail_before_processing(self):
        manifest = self.prepare()
        with ops.writer_lock(self.state):
            for command in [
                [
                    "run",
                    "--batch-id",
                    "batch",
                    "--manifest",
                    str(manifest),
                    "--source-root",
                    str(self.inputs),
                ],
                ["demo"],
            ]:
                child = subprocess.run(
                    [sys.executable, "-m", "src.ops", *command, "--state-dir", str(self.state)],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(child.returncode, 2)
                self.assertEqual(json.loads(child.stdout), {"error": "WORKER_BUSY"})
        value = json.loads(manifest.read_text())
        value["artifacts"][0]["path"] = "../outside.json"
        manifest.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ops.OpsError, "INPUT_PATH"):
            ops.run_batch("batch", manifest, state_dir=self.state, source_root=self.inputs)

    def test_database_error_and_publication_error_preserve_recovery_boundary(self):
        manifest = self.prepare()
        with patch.object(
            sqlite_ops, "sql_measures", side_effect=sqlite3.OperationalError("disk full")
        ):
            with self.assertRaisesRegex(ops.OpsError, "DATABASE_OPERATIONALERROR"):
                ops.run_batch("batch", manifest, state_dir=self.state, source_root=self.inputs)
        self.assertEqual(self.read("SELECT state FROM job")[0]["state"], "RUNNING")
        self.assertEqual(self.read("SELECT COUNT(*) AS n FROM combat_event")[0]["n"], 0)
        result = ops.run_batch("batch", state_dir=self.state)
        self.assertTrue(result["complete"])
        original = files.atomic_write_bytes

        def interrupted_publish(path, body):
            if path.name == "manifest.json":
                raise OSError("disk full")
            original(path, body)

        with patch.object(files, "atomic_write_bytes", side_effect=interrupted_publish):
            with self.assertRaises(OSError):
                ops.report_batch("batch", state_dir=self.state)
        self.assertFalse((self.state / "reports/batch/manifest.json").exists())
        report = ops.report_batch("batch", state_dir=self.state)
        self.assertEqual(report["attempts"], result["attempts"])
        self.assertTrue((self.state / "reports/batch/manifest.json").exists())

    def test_killed_worker_rolls_back_or_reuses_completed_transaction(self):
        script = """
import os,sys,sqlite3
from pathlib import Path
from unittest.mock import patch
from src import ops
from src.adapters import sqlite_ops, batch_inputs, files
from src.adapters.environment import Environment
state,phase=Path(sys.argv[1]),sys.argv[2]
class Connection(sqlite3.Connection):
    def commit(self):
        completed=self.execute("SELECT 1 FROM job WHERE state='SUCCEEDED'").fetchone()
        if completed and phase=='before_commit':
            os._exit(37)
        super().commit()
        if completed and phase=='after_commit':
            os._exit(37)
original=sqlite3.connect
original_load=batch_inputs.load_events_path
def connect(*args,**kwargs):
    return original(*args,**kwargs,factory=Connection)
def load(path, **kwargs):
    if phase=='after_claim':
        os._exit(37)
    return original_load(path, **kwargs)
with patch.object(sqlite_ops.sqlite3,'connect',side_effect=connect),patch.object(batch_inputs,'load_events_path',side_effect=load):
    ops.run_batch('batch',state_dir=state)
"""
        manifest = self.prepare()
        for phase in ("after_claim", "before_commit", "after_commit"):
            with self.subTest(phase=phase):
                self.state = self.root / phase
                self.register(manifest)
                child = subprocess.run(
                    [sys.executable, "-c", script, str(self.state), phase],
                    capture_output=True,
                    timeout=20,
                )
                self.assertEqual(child.returncode, 37, child.stderr.decode())
                self.assertEqual(
                    self.read("SELECT COUNT(*) AS n FROM review_case")[0]["n"],
                    2 if phase == "after_commit" else 0,
                )
                self.assertEqual(
                    self.read("SELECT COUNT(*) AS n FROM review_history")[0]["n"],
                    2 if phase == "after_commit" else 0,
                )
                result = ops.run_batch("batch", state_dir=self.state)
                self.assertTrue(result["complete"])
                self.assertEqual(result["metrics"]["attempts"], 1 if phase == "after_commit" else 2)
                self.assertEqual(self.read("SELECT COUNT(*) AS n FROM review_signal")[0]["n"], 2)
                self.assertEqual(self.read("SELECT COUNT(*) AS n FROM review_case")[0]["n"], 2)
                self.assertEqual(
                    self.read("SELECT COUNT(*) AS n FROM attempt WHERE outcome='SUCCEEDED'")[0][
                        "n"
                    ],
                    1,
                )
                if phase == "after_commit":
                    self.assertIsNone(result["attempts"][0]["elapsed_s"])
                    self.assertEqual(result["metrics"]["successful_duration_samples"], 0)


if __name__ == "__main__":
    unittest.main()
