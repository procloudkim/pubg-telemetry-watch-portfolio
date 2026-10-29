"""Batch commands and verified read models; persistence is supplied at composition."""

from .ports import (
    BatchInputSource,
    Clock,
    Environment,
    Files,
    OperationsPresentation,
    OperationsStore,
)
import hashlib
import json

from src.domain.errors import OpsError
from src.domain.identity import player_key
from src.domain.operations import _combat_rows, _compare, summarize
from src.domain.pubg.detection import detect_match, r2_observation
from src.domain.pubg.parsing import parse_events
from src.domain.review import REVIEW_STATES, next_state, validate_command
from src.domain.serialization import stable_json
from src.domain.tokens import validate_token


class Operations:
    def __init__(
        self,
        store: OperationsStore,
        inputs: BatchInputSource,
        files: Files,
        clock: Clock,
        environment: Environment,
        presentation: OperationsPresentation,
    ):
        self.store = store
        self.inputs = inputs
        self.files = files
        self.clock = clock
        self.environment = environment
        self.presentation = presentation

    def batch(self, batch_id):
        row = self.store.batch(batch_id)
        if row is None:
            raise OpsError("BATCH_NOT_FOUND")
        return row

    def register(self, batch_id, manifest_path, source_root):
        validate_token(batch_id, "batch_id")
        manifest_hash, protocol, inputs = self.inputs.read_inputs(manifest_path, source_root)
        code_hash = self.environment.fingerprint()
        snapshot = stable_json(inputs).decode()
        existing = self.store.batch(batch_id)
        if existing:
            if (
                existing["manifest_sha256"],
                existing["rule_protocol"],
                existing["code_sha256"],
                existing["manifest_json"],
            ) != (manifest_hash, protocol, code_hash, snapshot):
                raise OpsError("BATCH_INPUT_OR_CODE_CHANGED")
            return
        now = self.clock.now()
        runtime = self.environment.runtime()
        with self.store.transaction():
            self.store.add_batch(
                (
                    batch_id,
                    manifest_hash,
                    snapshot,
                    code_hash,
                    protocol,
                    now,
                    stable_json(runtime).decode(),
                )
            )
            for row in inputs:
                identity = [
                    row["source_sha256"],
                    row["match_id"],
                    protocol,
                    code_hash,
                    runtime["python"],
                    runtime["sqlite"],
                ]
                job_id = hashlib.sha256(stable_json(identity)).hexdigest()
                previous = self.store.job(job_id)
                if previous and any(
                    previous[key] != row[key]
                    for key in ("source_records", "source_bytes", "map_name", "mode")
                ):
                    raise OpsError("REUSED_JOB_METADATA_CHANGED")
                self.store.add_job(
                    (
                        job_id,
                        row["match_id"],
                        row["source_path"],
                        row["source_sha256"],
                        row["source_bytes"],
                        row["source_records"],
                        protocol,
                        code_hash,
                        row["map_name"],
                        row["mode"],
                        "QUEUED",
                        now,
                    )
                )
                self.store.link_job(batch_id, job_id)

    def recover(self):
        # The caller holds the process lock, proving that the previous worker exited.
        with self.store.transaction():
            self.store.recover(self.clock.now())

    def process(self, job):
        job_id = job["job_id"]
        started = self.clock.perf_counter()
        times, stage = {}, "load"
        attempt_no = self.store.next_attempt(job_id)
        with self.store.transaction():
            self.store.claim(job_id, attempt_no, self.clock.now())
        try:
            tick = self.clock.perf_counter()
            events = self.inputs.load(job)
            times[stage] = self.clock.perf_counter() - tick
            stage, tick = "parse_detect", self.clock.perf_counter()
            parsed = parse_events(job["match_id"], events, rule_protocol=job["rule_protocol"])
            keys = {
                name: player_key(job_id, name, player.get("account_id"))
                for name, player in parsed["players"].items()
            }
            if len(set(keys.values())) != len(keys):
                raise OpsError("PLAYER_KEY_COLLISION")
            expected = {}
            for name in keys:
                measure = r2_observation(parsed["players"], name=name)
                expected[keys[name]] = {
                    **measure,
                    "skip_reason": None if measure["status"] == "evaluated" else measure["status"],
                }
            signals = [
                {**signal, "player": "pla***", "player_key": keys[signal["player"]]}
                for signal in detect_match(parsed)
            ]
            # Reject nonfinite evidence before any results are persisted.
            json.dumps(parsed, allow_nan=False)
            json.dumps(signals, allow_nan=False)
            times[stage] = self.clock.perf_counter() - tick
            stage, tick = "sql", self.clock.perf_counter()
            self.store.begin(immediate=True)
            self.store.project(keys.values(), _combat_rows(events, job_id, keys))
            measures = self.store.measures(job_id, job["rule_protocol"])
            if set(expected) != {row["player_key"] for row in measures}:
                raise OpsError("SQL_PLAYER_SET")
            for measure in measures:
                _compare(expected[measure["player_key"]], measure)
            self.store.add_measures(job_id, measures)
            self.store.add_signals(job_id, signals)
            created = self.clock.now()
            for signal in signals:
                case_id = hashlib.sha256(
                    stable_json([job_id, signal["player_key"], signal["rule"]])
                ).hexdigest()
                self.store.add_case(case_id, job_id, signal, created)
            result_hash = hashlib.sha256(
                stable_json(
                    {
                        "measures": measures,
                        "signals": sorted(
                            signals, key=lambda row: (row["player_key"], row["rule"])
                        ),
                    }
                )
            ).hexdigest()
            times[stage] = self.clock.perf_counter() - tick
            stage, tick = "commit", self.clock.perf_counter()
            self.store.succeed(
                job_id,
                attempt_no,
                self.clock.now(),
                len(events),
                len(keys),
                result_hash,
                times,
                self.environment.peak_rss_kib(),
            )
            self.store.commit()
        except Exception as error:
            self.store.rollback()
            fatal = self.store.fatal_error(error)
            if fatal:
                raise OpsError(fatal) from None
            code = str(error) if isinstance(error, OpsError) else type(error).__name__.upper()
            with self.store.transaction():
                self.store.fail(
                    job_id,
                    attempt_no,
                    self.clock.now(),
                    stage,
                    code,
                    self.clock.perf_counter() - started,
                    times,
                    self.environment.peak_rss_kib(),
                )
        else:
            committed = self.clock.perf_counter()
            times[stage] = committed - tick
            # A missing post-commit metric must never undo successful processing.
            with self.store.transaction():
                self.store.record_timing(job_id, attempt_no, times, committed - started)

    def work(self, batch_id):
        batch = self.batch(batch_id)
        if batch["code_sha256"] != self.environment.fingerprint():
            raise OpsError("BATCH_CODE_CHANGED")
        previous_runtime = json.loads(batch["runtime_json"])
        if any(
            previous_runtime[key] != self.environment.runtime()[key] for key in ("python", "sqlite")
        ):
            raise OpsError("BATCH_RUNTIME_CHANGED")
        self.recover()
        for job in self.store.queued_jobs(batch_id):
            self.process(job)
        return self.status(batch_id)

    def retry(self, batch_id, job_id):
        if self.batch(batch_id)["code_sha256"] != self.environment.fingerprint():
            raise OpsError("BATCH_CODE_CHANGED")
        with self.store.transaction():
            if self.store.retry(batch_id, job_id) != 1:
                raise OpsError("FAILED_JOB_NOT_FOUND")

    def status(self, batch_id):
        with self.store.read_snapshot():
            return summarize(
                batch_id,
                dict(self.batch(batch_id)),
                self.store.jobs(batch_id),
                self.store.attempts(batch_id),
                self.clock.now(),
            )

    def review_list(self, batch_id=None, state=None):
        if state is not None and state not in REVIEW_STATES:
            raise OpsError("REVIEW_STATE")
        with self.store.read_snapshot():
            if batch_id is not None:
                self.batch(batch_id)
            return {
                "cases": self.store.review_list(batch_id, state),
                "batch_id": batch_id,
                "state": state,
            }

    def review_show(self, case_id):
        with self.store.read_snapshot():
            case = self.store.review_evidence(case_id)
            if case is None:
                raise OpsError("REVIEW_CASE_NOT_FOUND")
            value = dict(case)
            signal = json.loads(value.pop("signal_json"))
            return {"case": value, "signal": signal, "history": self.store.review_history(case_id)}

    def review_change(self, action, case_id, operator, note=None):
        operator, note = validate_command(action, operator, note)
        with self.store.transaction():
            self.store.begin(immediate=True)
            case = self.store.review_case(case_id)
            if case is None:
                raise OpsError("REVIEW_CASE_NOT_FOUND")
            previous = case["state"]
            state = next_state(action, previous)
            now = self.clock.now()
            sequence = self.store.next_review_sequence(case_id)
            self.store.change_review(
                case_id,
                state,
                now,
                (case_id, sequence, action, operator, now, previous, state, note),
            )
            self.store.commit()
        return {"case_id": case_id, "state": state, "action": action, "sequence": sequence}

    def report(self, batch_id, destination):
        validate_token(batch_id, "batch_id")
        with self.store.read_snapshot():
            summary = self.status(batch_id)
            groups, failures, recoveries, signals, selection = self.store.report_rows(batch_id)
        summary.update(groups=groups, failures=failures, recovered_or_repeated=recoveries)
        self.files.write_bytes(destination / "operations.json", stable_json(summary))
        self.files.write_bytes(
            destination / "operations.md", self.presentation.render_operations(batch_id, summary)
        )
        if summary["complete"]:
            finished = max(row["finished_at"] for row in selection)
            review = self.presentation.render_review(signals, selection, generated_at=finished)
            self.files.write_bytes(destination / "review-queue.md", review)
            manifest = {
                "schema_version": 1,
                "batch_id": batch_id,
                "quality": {"status": "PASS"},
                "input_manifest_sha256": summary["manifest_sha256"],
                "code_sha256": summary["code_sha256"],
                "rule_protocol": summary["rule_protocol"],
                "jobs": selection,
                "reports": {
                    name: self.files.hash(destination / name)
                    for name in ("operations.json", "operations.md", "review-queue.md")
                },
            }
            # The manifest is the publication marker and must be written last.
            self.files.write_bytes(destination / "manifest.json", stable_json(manifest))
        return summary
