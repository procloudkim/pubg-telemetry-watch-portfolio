"""SQLite schema-v2 persistence; application owns transaction sequencing."""

from contextlib import contextmanager
import json
import math
import sqlite3
from .files import ROOT
from src.domain.errors import OpsError
from src.domain.operations import MEASURE_FIELDS
from src.domain.pubg.detection import MIN_ATTACKS, MIN_R2_POOL, MIN_R2_SIGNAL_POOL, Z_HIT
from src.domain.pubg.parsing import LEGACY_RULE_PROTOCOL_VERSION
from src.domain.serialization import stable_json

SQL_PATH = ROOT / "sql/ops.sql"


@contextmanager
def writer_lock(state_dir):
    import fcntl

    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state_dir / "worker.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise OpsError("WORKER_BUSY") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def connect(state_dir, *, readonly=False):
    path = state_dir / "ops.sqlite3"
    if readonly:
        if not path.is_file():
            raise OpsError("STATE_NOT_FOUND")
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    else:
        connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version == 0 and not readonly:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
            connection.close()
            raise OpsError("UNKNOWN_DATABASE_SCHEMA")
        connection.executescript(SQL_PATH.read_text(encoding="utf-8").split("-- @compute")[0])
    elif version != 2:
        connection.close()
        raise OpsError("UNSUPPORTED_DATABASE_SCHEMA")
    if not readonly:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("CREATE TEMP TABLE input_player (player_key TEXT PRIMARY KEY NOT NULL)")
        connection.create_function(
            "SQRT", 1, lambda value: None if value is None else math.sqrt(value), deterministic=True
        )
    return connection


def sql_measures(connection, job_id, protocol):
    parameters = {
        "job_id": job_id,
        "legacy": protocol == LEGACY_RULE_PROTOCOL_VERSION,
        "min_attacks": MIN_ATTACKS,
        "min_pool": MIN_R2_POOL,
        "min_signal_pool": MIN_R2_SIGNAL_POOL,
        "z_hit": Z_HIT,
    }
    query = SQL_PATH.read_text(encoding="utf-8").split("-- @compute")[1]
    return [dict(row) for row in connection.execute(query, parameters)]


class SQLiteStore:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def transaction(self):
        with self.connection:
            yield

    @contextmanager
    def read_snapshot(self):
        owned = not self.connection.in_transaction
        if owned:
            self.begin()
        try:
            yield
        finally:
            # A borrowed transaction and its pending writes belong to the caller.
            if owned:
                self.rollback()

    def begin(self, *, immediate=False):
        self.connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def fatal_error(self, error):
        if isinstance(error, sqlite3.Error) and not isinstance(error, sqlite3.IntegrityError):
            return "DATABASE_" + type(error).__name__.upper()
        return None

    def batch(self, batch_id):
        return self.connection.execute(
            "SELECT * FROM batch WHERE batch_id=?", (batch_id,)
        ).fetchone()

    def add_batch(self, values):
        self.connection.execute("INSERT INTO batch VALUES (?,?,?,?,?,?,?)", values)

    def job(self, job_id):
        return self.connection.execute("SELECT * FROM job WHERE job_id=?", (job_id,)).fetchone()

    def add_job(self, values):
        self.connection.execute(
            """INSERT INTO job (job_id,match_id,source_path,source_sha256,source_bytes,
                source_records,rule_protocol,code_sha256,map_name,mode,state,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_id) DO NOTHING""",
            values,
        )

    def link_job(self, batch_id, job_id):
        self.connection.execute("INSERT INTO batch_job VALUES (?,?)", (batch_id, job_id))

    def recover(self, now):
        self.connection.execute(
            """UPDATE attempt SET outcome='INTERRUPTED', recovered_at=?, error_code='PROCESS_INTERRUPTED'
                              WHERE outcome='RUNNING'""",
            (now,),
        )
        self.connection.execute("UPDATE job SET state='QUEUED' WHERE state='RUNNING'")

    def next_attempt(self, job_id):
        return self.connection.execute(
            "SELECT COALESCE(MAX(attempt_no),0)+1 FROM attempt WHERE job_id=?", (job_id,)
        ).fetchone()[0]

    def claim(self, job_id, attempt_no, now):
        self.connection.execute(
            "UPDATE job SET state='RUNNING' WHERE job_id=? AND state='QUEUED'", (job_id,)
        )
        self.connection.execute(
            "INSERT INTO attempt (job_id,attempt_no,started_at,outcome,stage) VALUES (?,?,?,?,?)",
            (job_id, attempt_no, now, "RUNNING", "load"),
        )

    def project(self, keys, combat_rows):
        self.connection.execute("DELETE FROM input_player")
        self.connection.executemany("INSERT INTO input_player VALUES (?)", ((key,) for key in keys))
        self.connection.executemany("INSERT INTO combat_event VALUES (?,?,?,?,?,?,?)", combat_rows)

    def measures(self, job_id, protocol):
        return sql_measures(self.connection, job_id, protocol)

    def add_measures(self, job_id, measures):
        columns = ("job_id", "player_key", *MEASURE_FIELDS)
        # Identifiers come only from this fixed contract; all values remain bound.
        self.connection.executemany(
            "INSERT INTO player_match ("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join("?" for _ in columns)
            + ")",
            (
                (job_id, row["player_key"], *(row[field] for field in MEASURE_FIELDS))
                for row in measures
            ),
        )

    def add_signals(self, job_id, signals):
        self.connection.executemany(
            "INSERT INTO review_signal VALUES (?,?,?,?)",
            (
                (job_id, signal["player_key"], signal["rule"], stable_json(signal).decode())
                for signal in signals
            ),
        )

    def add_case(self, case_id, job_id, signal, created):
        self.connection.execute(
            "INSERT INTO review_case VALUES (?,?,?,?,?,?,?)",
            (case_id, job_id, signal["player_key"], signal["rule"], "OPEN", created, created),
        )
        self.connection.execute(
            "INSERT INTO review_history VALUES (?,?,?,?,?,?,?,?)",
            (case_id, 1, "created", "system", created, None, "OPEN", None),
        )

    def succeed(
        self, job_id, attempt_no, finished, event_count, player_count, result_hash, times, rss
    ):
        self.connection.execute(
            """UPDATE job SET state='SUCCEEDED',finished_at=?,event_count=?,player_count=?,result_sha256=?
                              WHERE job_id=?""",
            (finished, event_count, player_count, result_hash, job_id),
        )
        self.connection.execute(
            """UPDATE attempt SET outcome='SUCCEEDED',finished_at=?,stage='commit',elapsed_s=NULL,
            stage_seconds_json=?,process_peak_rss_kib=? WHERE job_id=? AND attempt_no=?""",
            (finished, stable_json(times).decode(), rss, job_id, attempt_no),
        )

    def fail(self, job_id, attempt_no, now, stage, code, elapsed, times, rss):
        self.connection.execute("UPDATE job SET state='FAILED' WHERE job_id=?", (job_id,))
        self.connection.execute(
            """UPDATE attempt SET outcome='FAILED',finished_at=?,stage=?,error_code=?,
                elapsed_s=?,stage_seconds_json=?,process_peak_rss_kib=? WHERE job_id=? AND attempt_no=?""",
            (now, stage, code, elapsed, stable_json(times).decode(), rss, job_id, attempt_no),
        )

    def record_timing(self, job_id, attempt_no, times, elapsed):
        self.connection.execute(
            "UPDATE attempt SET stage_seconds_json=?,elapsed_s=? WHERE job_id=? AND attempt_no=?",
            (stable_json(times).decode(), elapsed, job_id, attempt_no),
        )

    def queued_jobs(self, batch_id):
        return self.connection.execute(
            """SELECT j.* FROM job j JOIN batch_job b USING(job_id)
        WHERE b.batch_id=? AND j.state='QUEUED' ORDER BY j.match_id,j.job_id""",
            (batch_id,),
        ).fetchall()

    def retry(self, batch_id, job_id):
        return self.connection.execute(
            """UPDATE job SET state='QUEUED' WHERE job_id=? AND state='FAILED'
                AND EXISTS (SELECT 1 FROM batch_job WHERE batch_id=? AND job_id=job.job_id)""",
            (job_id, batch_id),
        ).rowcount

    def jobs(self, batch_id):
        return [
            dict(row)
            for row in self.connection.execute(
                """SELECT j.* FROM job j JOIN batch_job b USING(job_id)
        WHERE b.batch_id=? ORDER BY j.match_id,j.job_id""",
                (batch_id,),
            )
        ]

    def attempts(self, batch_id):
        return [
            dict(row)
            for row in self.connection.execute(
                """SELECT a.* FROM attempt a JOIN batch_job b USING(job_id)
        WHERE b.batch_id=? ORDER BY a.started_at,a.job_id,a.attempt_no""",
                (batch_id,),
            )
        ]

    def review_list(self, batch_id, state):
        return [
            dict(row)
            for row in self.connection.execute(
                """SELECT c.*,j.match_id FROM review_case c
            JOIN job j USING(job_id) WHERE (? IS NULL OR c.state=?) AND
            (? IS NULL OR EXISTS (SELECT 1 FROM batch_job b WHERE b.job_id=c.job_id AND b.batch_id=?))
            ORDER BY c.created_at,c.case_id""",
                (state, state, batch_id, batch_id),
            )
        ]

    def review_evidence(self, case_id):
        return self.connection.execute(
            """SELECT c.*,j.match_id,s.signal_json FROM review_case c
            JOIN job j USING(job_id) JOIN review_signal s USING(job_id,player_key,rule)
            WHERE c.case_id=?""",
            (case_id,),
        ).fetchone()

    def review_history(self, case_id):
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM review_history WHERE case_id=? ORDER BY sequence", (case_id,)
            )
        ]

    def review_case(self, case_id):
        return self.connection.execute(
            "SELECT * FROM review_case WHERE case_id=?", (case_id,)
        ).fetchone()

    def next_review_sequence(self, case_id):
        return self.connection.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM review_history WHERE case_id=?", (case_id,)
        ).fetchone()[0]

    def change_review(self, case_id, state, now, history):
        self.connection.execute(
            "UPDATE review_case SET state=?,updated_at=? WHERE case_id=?", (state, now, case_id)
        )
        self.connection.execute("INSERT INTO review_history VALUES (?,?,?,?,?,?,?,?)", history)

    def report_rows(self, batch_id):
        groups = [
            dict(row)
            for row in self.connection.execute(
                """SELECT j.map_name,j.mode,p.status,COUNT(*) AS player_matches,
            SUM(p.review_candidate) AS review_candidates FROM player_match p JOIN job j USING(job_id)
            JOIN batch_job b USING(job_id) WHERE b.batch_id=? AND j.state='SUCCEEDED'
            GROUP BY j.map_name,j.mode,p.status ORDER BY j.map_name,j.mode,p.status""",
                (batch_id,),
            )
        ]
        failures = [
            dict(row)
            for row in self.connection.execute(
                """SELECT a.stage,a.error_code,COUNT(*) AS attempts
            FROM attempt a JOIN batch_job b USING(job_id) WHERE b.batch_id=? AND a.error_code IS NOT NULL
            GROUP BY a.stage,a.error_code ORDER BY a.stage,a.error_code""",
                (batch_id,),
            )
        ]
        recoveries = [
            dict(row)
            for row in self.connection.execute(
                """WITH ranked AS (
            SELECT a.*,ROW_NUMBER() OVER (PARTITION BY a.job_id ORDER BY a.attempt_no DESC) AS latest
            FROM attempt a JOIN batch_job b USING(job_id) WHERE b.batch_id=?)
            SELECT job_id,attempt_no,outcome,error_code FROM ranked
            WHERE latest=1 AND attempt_no>1 ORDER BY job_id""",
                (batch_id,),
            )
        ]
        signals = [
            json.loads(row[0])
            for row in self.connection.execute(
                """SELECT s.signal_json FROM review_signal s
            JOIN batch_job b USING(job_id) WHERE b.batch_id=? ORDER BY s.job_id,s.player_key,s.rule""",
                (batch_id,),
            )
        ]
        selection = [
            dict(row)
            for row in self.connection.execute(
                """SELECT j.match_id,j.mode,j.map_name AS map,j.finished_at,
            j.source_sha256,j.result_sha256 FROM job j JOIN batch_job b USING(job_id)
            WHERE b.batch_id=? ORDER BY j.match_id,j.job_id""",
                (batch_id,),
            )
        ]
        return groups, failures, recoveries, signals, selection
