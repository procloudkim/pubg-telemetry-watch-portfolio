"""Read-only benchmark provenance and synthetic actor mapping."""

import json
from src.domain.identity import player_key
from src.domain.pubg.parsing import LEGACY_RULE_PROTOCOL_VERSION
from src.domain.pubg.detection import MIN_ATTACKS, MIN_R2_POOL, MIN_R2_SIGNAL_POOL, Z_HIT
from .sqlite_ops import SQL_PATH


def synthetic_results(connection):
    """Map this generator's actors across code/runtime-dependent job identities."""
    result = []
    for job in connection.execute("SELECT job_id,match_id FROM job ORDER BY match_id"):
        actors = {
            player_key(job["job_id"], f"synthetic_{p}", f"synthetic-id-{p}"): f"synthetic-id-{p}"
            for p in range(100)
        }
        measures = []
        for row in connection.execute(
            "SELECT * FROM player_match WHERE job_id=?", (job["job_id"],)
        ):
            value = dict(row)
            del value["job_id"]
            value["actor"] = actors[value.pop("player_key")]
            measures.append(value)
        signals = []
        for row in connection.execute(
            "SELECT signal_json FROM review_signal WHERE job_id=?", (job["job_id"],)
        ):
            value = json.loads(row[0])
            value["actor"] = actors[value.pop("player_key")]
            signals.append(value)
        result.append(
            {
                "match_id": job["match_id"],
                "measures": sorted(measures, key=lambda r: r["actor"]),
                "signals": sorted(signals, key=lambda r: (r["actor"], r["rule"])),
            }
        )
    return result


def query_plan(connection, result):
    return [
        row[3]
        for row in connection.execute(
            "EXPLAIN QUERY PLAN " + SQL_PATH.read_text(encoding="utf-8").split("-- @compute")[1],
            {
                "job_id": result["jobs"][0]["job_id"],
                "legacy": result["rule_protocol"] == LEGACY_RULE_PROTOCOL_VERSION,
                "min_attacks": MIN_ATTACKS,
                "min_pool": MIN_R2_POOL,
                "min_signal_pool": MIN_R2_SIGNAL_POOL,
                "z_hit": Z_HIT,
            },
        )
    ]
