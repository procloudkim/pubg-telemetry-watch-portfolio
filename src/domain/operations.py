"""Operational projection and parity checks without resource access."""

import json
import math
from datetime import datetime, timezone
from .errors import OpsError
from .pubg.parsing import LEGACY_RULE_PROTOCOL_VERSION, RULE_PROTOCOL_VERSION

PROTOCOLS = {
    "v1-rules-1": LEGACY_RULE_PROTOCOL_VERSION,
    "v1-rules-event-context-2": RULE_PROTOCOL_VERSION,
    "v2-r2-baseline-2": LEGACY_RULE_PROTOCOL_VERSION,
    "v2-r2-baseline-3": RULE_PROTOCOL_VERSION,
    "v3-r2-top100-2": LEGACY_RULE_PROTOCOL_VERSION,
    "v3-r2-top100-3": RULE_PROTOCOL_VERSION,
}
MEASURE_FIELDS = (
    "attacks",
    "damage_events",
    "ratio",
    "review_candidate",
    "minimum_signal_pool",
    "status",
    "eligible_players",
    "match_mean",
    "match_sd",
    "local_z",
    "skip_reason",
)
STATES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED")


def _combat_rows(events, job_id, keys):
    for index, event in enumerate(events):
        kind = {"LogPlayerAttack": "attack", "LogPlayerTakeDamage": "damage"}.get(event.get("_T"))
        if not kind:
            continue
        actor = event.get("attacker") or {}
        name = actor.get("name")
        if not name:
            continue
        attack = event.get("attackId")
        if attack is not None and type(attack) is not int:
            raise OpsError("ATTACK_ID_TYPE")
        damage = float(event.get("damage") or 0) if kind == "damage" else None
        if damage is not None and not math.isfinite(damage):
            raise OpsError("NONFINITE_DAMAGE")
        event_time = event.get("_D")
        if event_time is not None:
            value = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
            if value.tzinfo is None:
                raise OpsError("EVENT_TIME_OFFSET")
            event_time = value.astimezone(timezone.utc).isoformat()
        yield (
            job_id,
            index,
            keys[name],
            kind,
            str(attack) if attack is not None else None,
            damage,
            event_time,
        )


def _compare(expected, observed):
    for field in MEASURE_FIELDS:
        left, right = expected[field], observed[field]
        if (
            field in {"ratio", "match_mean", "match_sd", "local_z"}
            and left is not None
            and right is not None
        ):
            same = math.isfinite(right) and math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
        else:
            same = left == right
        if not same:
            raise OpsError("SQL_PARITY_" + field.upper())


def summarize(batch_id, batch, jobs, attempts, now):
    counts = {state: sum(row["state"] == state for row in jobs) for state in STATES}
    durations = sorted(
        row["elapsed_s"]
        for row in attempts
        if row["outcome"] == "SUCCEEDED" and row["elapsed_s"] is not None
    )
    total_seconds = sum(row["elapsed_s"] or 0 for row in attempts)
    event_count = sum(row["event_count"] or 0 for row in jobs)
    inputs = json.loads(batch["manifest_json"])
    queued = [row["created_at"] for row in jobs if row["state"] == "QUEUED"]
    metrics = {
        "input_encoding_counts": {
            kind: sum(row["input_encoding"] == kind for row in inputs) for kind in ("json", "gzip")
        },
        "oldest_queued_seconds": max(
            0, (datetime.fromisoformat(now) - datetime.fromisoformat(min(queued))).total_seconds()
        )
        if queued
        else None,
        "events": event_count,
        "input_bytes": sum(row["source_bytes"] for row in jobs),
        "completed_input_bytes": sum(
            row["source_bytes"] for row in jobs if row["state"] == "SUCCEEDED"
        ),
        "attempts": len(attempts),
        "retries": sum(row["attempt_no"] > 1 for row in attempts),
        "measured_attempt_seconds": total_seconds,
        "events_per_measured_second": event_count / total_seconds
        if total_seconds and len(durations) == counts["SUCCEEDED"]
        else None,
        "successful_duration_samples": len(durations),
        "median_match_s": (durations[(len(durations) - 1) // 2] + durations[len(durations) // 2])
        / 2
        if durations
        else None,
        "p95_match_s": durations[math.ceil(0.95 * len(durations)) - 1] if durations else None,
        "process_peak_rss_kib": max(
            (row["process_peak_rss_kib"] or 0 for row in attempts), default=0
        ),
    }
    safe_jobs = [
        {
            key: row[key]
            for key in (
                "job_id",
                "match_id",
                "state",
                "event_count",
                "player_count",
                "result_sha256",
            )
        }
        for row in jobs
    ]
    return {
        "batch_id": batch_id,
        "complete": counts["SUCCEEDED"] == len(jobs),
        "counts": counts,
        "rule_protocol": batch["rule_protocol"],
        "code_sha256": batch["code_sha256"],
        "manifest_sha256": batch["manifest_sha256"],
        "created_at": batch["created_at"],
        "runtime": json.loads(batch["runtime_json"]),
        "metrics": metrics,
        "jobs": safe_jobs,
        "attempts": attempts,
    }
