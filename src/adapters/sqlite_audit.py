"""In-memory SQLite reconstruction of the frozen v3 audit schema."""

import sqlite3
from pathlib import Path
from .files import ROOT

SQL_PATH = ROOT / "sql/v3_audit.sql"
LOAD_BOUNDARY = "-- @load-boundary"


def _schema_parts(sql_path: Path):
    sql = sql_path.read_text(encoding="utf-8")
    if sql.count(LOAD_BOUNDARY) != 1:
        raise ValueError("SQL load boundary는 정확히 1개여야 함")
    return sql.split(LOAD_BOUNDARY, 1)


def _insert_rows(connection, run_id, manifest, observations, source_hashes):
    connection.execute(
        "INSERT INTO run_meta VALUES (?, ?, ?, ?, ?, ?)",
        (
            run_id,
            manifest["protocol_version"],
            source_hashes["manifest"],
            source_hashes["observations"],
            source_hashes["validation"],
            "PASS",
        ),
    )
    columns = (
        "run_id",
        "observation_id",
        "match_id",
        "player_key",
        "rank",
        "rank_decile",
        "split",
        "recent_index",
        "season_id",
        "mode",
        "map_name",
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
    placeholders = ",".join("?" for _ in columns)
    connection.executemany(
        f"INSERT INTO stg_r2_observation ({','.join(columns)}) VALUES ({placeholders})",
        [
            (
                run_id,
                row["observation_id"],
                row["match_id"],
                row["player_key"],
                row["rank"],
                row["rank_decile"],
                row["split"],
                row["recent_index"],
                row["season_id"],
                row["mode"],
                row["map"],
                row["attacks"],
                row["damage_events"],
                row["ratio"],
                int(row["review_candidate"]),
                row["minimum_signal_pool"],
                row["status"],
                row["eligible_players"],
                row["match_mean"],
                row["match_sd"],
                row["local_z"],
                row["skip_reason"],
            )
            for row in observations
        ],
    )
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("manifest artifacts 형식 오류")
    connection.executemany(
        "INSERT INTO artifact VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                run_id,
                row["path"],
                row["layer"],
                row["dataset"],
                row["media_type"],
                row["bytes"],
                row["records"],
                row["sha256"],
            )
            for row in artifacts
        ],
    )
    lineage = []
    for row in artifacts:
        sources = row.get("derived_from")
        if not isinstance(sources, list):
            raise ValueError("manifest derived_from 형식 오류")
        lineage.extend((run_id, row["path"], source) for source in sources)
    connection.executemany("INSERT INTO lineage_edge VALUES (?, ?, ?)", lineage)


def _row(connection, view):
    if view not in {"v_observation_funnel", "v_primary_first_evaluated", "v_lineage_reachability"}:
        raise ValueError("Unknown audit view")
    row = connection.execute(f"SELECT * FROM {view}").fetchone()
    if row is None:
        raise RuntimeError(f"SQL 결과 없음: {view}")
    return dict(row)


def _group_rows(connection, view, key):
    if (view, key) not in {("v_decile_coverage", "rank_decile"), ("v_map_coverage", "map_name")}:
        raise ValueError("Unknown audit grouping")
    return {
        str(row[key]): dict(row)
        for row in connection.execute(f"SELECT * FROM {view} ORDER BY {key}")
    }


class SQLiteAudit:
    def calculate(self, run_id, manifest, observations, source_hashes, sql_path):
        schema, transform = _schema_parts(sql_path)
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(schema)
            with connection:
                _insert_rows(connection, run_id, manifest, observations, source_hashes)
            connection.executescript(transform)
            summary = {
                "run_id": run_id,
                "protocol_version": manifest["protocol_version"],
                "source_sha256": source_hashes,
                "schema": {
                    "players": connection.execute("SELECT COUNT(*) FROM dim_player").fetchone()[0],
                    "matches": connection.execute("SELECT COUNT(*) FROM dim_match").fetchone()[0],
                    "observations": connection.execute(
                        "SELECT COUNT(*) FROM fact_r2_observation"
                    ).fetchone()[0],
                },
                "funnel": _row(connection, "v_observation_funnel"),
                "primary": _row(connection, "v_primary_first_evaluated"),
                "deciles": _group_rows(connection, "v_decile_coverage", "rank_decile"),
                "maps": _group_rows(connection, "v_map_coverage", "map_name"),
                "lineage": _row(connection, "v_lineage_reachability"),
            }
        finally:
            connection.close()
        return summary
