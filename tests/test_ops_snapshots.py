"""Exercise query lifetime through Operations and caller-owned SQLite transactions."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src import ops
from src.adapters.files import ROOT, LocalFiles
from src.cli.ops_composition import operations
from src.ops_demo import write_inputs


class ReadSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        inputs = self.root / "inputs"
        fixture = json.loads(
            (ROOT / "tests/fixtures/TESTMATCH.telemetry.json").read_text(encoding="utf-8")
        )
        manifest = write_inputs(inputs, [("TESTMATCH", fixture)])
        ops.run_batch("batch", manifest, state_dir=self.state, source_root=inputs)
        self.case = ops.review_list(state_dir=self.state)["cases"][0]["case_id"]

    def test_review_queries_release_owned_snapshots_and_allow_reuse(self):
        with closing(ops.connect(self.state, readonly=True)) as connection:
            service = operations(connection)
            for _ in range(2):
                self.assertEqual(len(service.review_list(batch_id="batch")["cases"]), 2)
                self.assertFalse(connection.in_transaction)
                self.assertEqual(service.review_show(self.case)["case"]["state"], "OPEN")
                self.assertFalse(connection.in_transaction)

    def test_status_reads_one_snapshot_while_another_connection_commits(self):
        with closing(ops.connect(self.state, readonly=True)) as baseline_connection:
            baseline = operations(baseline_connection).status("batch")
        with closing(ops.connect(self.state, readonly=True)) as reader:
            with closing(ops.connect(self.state)) as writer:
                changed = []

                def concurrent_commit(action, table, column, database, trigger):
                    if action == sqlite3.SQLITE_READ and table == "attempt" and not changed:
                        with writer:
                            writer.execute("UPDATE job SET event_count=event_count+1")
                            writer.execute("UPDATE attempt SET elapsed_s=?", (7.0,))
                        changed.append(True)
                    return sqlite3.SQLITE_OK

                reader.set_authorizer(concurrent_commit)
                service = operations(reader)
                result = service.status("batch")
                reader.set_authorizer(lambda *args: sqlite3.SQLITE_OK)  # None needs Python 3.11.
                self.assertEqual(changed, [True])
                self.assertEqual(result["metrics"], baseline["metrics"])
                self.assertFalse(reader.in_transaction)
                self.assertEqual(service.status("batch")["metrics"]["events"], 54)

    def test_queries_preserve_caller_transactions_and_pending_changes(self):
        for write in (False, True):
            with self.subTest(write=write), closing(ops.connect(self.state)) as connection:
                service = operations(connection)
                original = service.status("batch")["created_at"]
                pending = "2000-01-01T00:00:00+00:00" if write else original
                connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                if write:
                    connection.execute(
                        "UPDATE batch SET created_at=? WHERE batch_id=?", (pending, "batch")
                    )
                self.assertEqual(len(service.review_list()["cases"]), 2)
                self.assertEqual(service.review_show(self.case)["case"]["state"], "OPEN")
                self.assertEqual(service.status("batch")["created_at"], pending)
                result = service.report("batch", self.root / str(write))
                self.assertEqual(result["created_at"], pending)
                with self.assertRaisesRegex(ops.OpsError, "REVIEW_CASE_NOT_FOUND"):
                    service.review_show("missing")
                self.assertTrue(connection.in_transaction)
                self.assertEqual(service.status("batch")["created_at"], pending)
                connection.rollback()
                self.assertEqual(service.status("batch")["created_at"], original)

    def test_missing_rows_release_owned_snapshots_before_the_next_query(self):
        with closing(ops.connect(self.state, readonly=True)) as connection:
            service = operations(connection)
            queries = [
                (lambda: service.review_list(batch_id="missing"), "BATCH_NOT_FOUND"),
                (lambda: service.review_show("missing"), "REVIEW_CASE_NOT_FOUND"),
                (lambda: service.status("missing"), "BATCH_NOT_FOUND"),
                (lambda: service.report("missing", self.root / "missing"), "BATCH_NOT_FOUND"),
            ]
            for query, error in queries:
                with self.subTest(error=error), self.assertRaisesRegex(ops.OpsError, error):
                    query()
                self.assertFalse(connection.in_transaction)
                self.assertEqual(service.review_show(self.case)["case"]["state"], "OPEN")
            self.assertFalse((self.root / "missing").exists())

    def test_database_errors_respect_snapshot_ownership_and_allow_reuse(self):
        for borrowed in (False, True):
            with self.subTest(borrowed=borrowed), closing(
                ops.connect(self.state)
            ) as connection:
                service = operations(connection)
                original = service.status("batch")["created_at"]
                pending = "2000-01-01T00:00:00+00:00" if borrowed else original
                if borrowed:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "UPDATE batch SET created_at=? WHERE batch_id=?", (pending, "batch")
                    )
                queries = [
                    lambda: service.review_list(),
                    lambda: service.review_show(self.case),
                    lambda: service.status("batch"),
                    lambda: service.report("batch", self.root / "denied"),
                ]
                for query in queries:
                    connection.set_authorizer(
                        lambda action, *args: sqlite3.SQLITE_DENY
                        if action == sqlite3.SQLITE_READ
                        else sqlite3.SQLITE_OK
                    )
                    with self.assertRaises(sqlite3.DatabaseError):
                        query()
                    connection.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
                    self.assertEqual(connection.in_transaction, borrowed)
                    self.assertEqual(service.review_show(self.case)["case"]["state"], "OPEN")
                    self.assertEqual(service.status("batch")["created_at"], pending)
                self.assertFalse((self.root / "denied").exists())

    def test_report_keeps_one_snapshot_and_releases_it_before_publishing(self):
        with closing(ops.connect(self.state, readonly=True)) as reader:
            with closing(ops.connect(self.state)) as writer:
                changed, published = [], []

                def concurrent_commit(action, table, column, database, trigger):
                    if action == sqlite3.SQLITE_READ and table == "player_match" and not changed:
                        with writer:
                            writer.execute("UPDATE job SET result_sha256=?", ("1" * 64,))
                        changed.append(True)
                    return sqlite3.SQLITE_OK

                class PublishingFiles(LocalFiles):
                    def write_bytes(self, path, data):
                        published.append(reader.in_transaction)
                        super().write_bytes(path, data)

                reader.set_authorizer(concurrent_commit)
                service = operations(reader)
                service.files = PublishingFiles()
                destination = self.root / "report"
                summary = service.report("batch", destination)
                reader.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
                manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(changed, [True])
                self.assertEqual(
                    summary["jobs"][0]["result_sha256"], manifest["jobs"][0]["result_sha256"]
                )
                self.assertNotEqual(manifest["jobs"][0]["result_sha256"], "1" * 64)
                self.assertTrue(published)
                self.assertFalse(any(published))
                self.assertFalse(reader.in_transaction)
                self.assertEqual(service.status("batch")["jobs"][0]["result_sha256"], "1" * 64)
