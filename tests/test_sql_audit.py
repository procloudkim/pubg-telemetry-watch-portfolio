import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.common import sha256_file
from src.sql_audit import SQL_PATH, audit_run
from src.adapters.files import LocalFiles
from src.adapters.sqlite_audit import _row, _group_rows


RUN_ID = "sql-test-run"
PROTOCOL = "v3-r2-top100-2"


def observation(
    observation_id,
    match_id,
    player_key,
    rank,
    recent_index,
    status,
    *,
    candidate=False,
    map_name="Arena_Main",
):
    evaluated = status == "evaluated"
    target_low = status == "target_below_min_attacks"
    eligible = None if target_low else 20 if evaluated else 10
    attacks = 10 if target_low else 40
    damage_events = 2 if target_low else 20
    return {
        "observation_id": observation_id,
        "match_id": match_id,
        "player_key": player_key,
        "rank": rank,
        "rank_decile": (rank - 1) // 10 + 1,
        "split": "holdout",
        "recent_index": recent_index,
        "season_id": "season-test",
        "mode": "squad-fpp",
        "map": map_name,
        "attacks": attacks,
        "damage_events": damage_events,
        "ratio": damage_events / attacks,
        "review_candidate": candidate,
        "minimum_signal_pool": 11,
        "status": status,
        "eligible_players": eligible,
        "match_mean": None if target_low else 0.4,
        "match_sd": None if target_low else 0.1,
        "local_z": 1.0 if evaluated else None,
        "skip_reason": None if evaluated else status,
    }


class SqlAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.report = self.root / "reports" / "sql-audit.md"
        self.observations = [
            observation("o1", "m1", "a" * 24, 11, 2, "evaluated", candidate=True),
            observation("o2", "m2", "a" * 24, 11, 1, "evaluated"),
            observation("o3", "m3", "b" * 24, 21, 1, "target_below_min_attacks"),
            observation("o4", "m4", "c" * 24, 31, 1, "match_pool_below_signal_capable"),
            observation("o5", "m5", "d" * 24, 41, 1, "evaluated", map_name="Desert_Main"),
        ]

    def tearDown(self):
        self.temporary.cleanup()

    def write_fixture(self, *, observations=None, gold_evaluated=3):
        observations = self.observations if observations is None else observations
        observation_path = self.root / "data" / "silver" / "v3" / RUN_ID / "observations.json"
        validation_path = self.root / "data" / "gold" / "v3" / RUN_ID / "validation.json"
        raw_path = self.root / "data" / "bronze" / "v3" / RUN_ID / "raw.json"
        for path in (observation_path, validation_path, raw_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        observation_path.write_text(json.dumps(observations), encoding="utf-8")
        validation = {
            "run_id": RUN_ID,
            "protocol_version": PROTOCOL,
            "denominators": {
                "accepted_observations": 5,
                "evaluated": gold_evaluated,
                "target_below_min_attacks": 1,
                "match_pool_below_8": 0,
                "match_pool_below_signal_capable": 1,
            },
            "primary": {"evaluated_players": 2, "review_candidates": 0},
            "secondary": {"evaluated": gold_evaluated, "review_candidates": 1},
            "by_map": {
                "Arena_Main": {"evaluated": 2, "review_candidates": 1},
                "Desert_Main": {"evaluated": 1, "review_candidates": 0},
            },
            "by_rank_decile": {
                "2": {"evaluated": 2, "review_candidates": 1},
                "5": {"evaluated": 1, "review_candidates": 0},
            },
        }
        validation_path.write_text(json.dumps(validation), encoding="utf-8")
        raw_path.write_text("{}", encoding="utf-8")
        artifacts = [
            {
                "layer": "bronze",
                "dataset": "raw_fixture",
                "path": raw_path.relative_to(self.root).as_posix(),
                "media_type": "application/json",
                "bytes": raw_path.stat().st_size,
                "records": 1,
                "sha256": sha256_file(raw_path),
                "derived_from": [],
            },
            {
                "layer": "silver",
                "dataset": "r2_observations",
                "path": observation_path.relative_to(self.root).as_posix(),
                "media_type": "application/json",
                "bytes": observation_path.stat().st_size,
                "records": len(observations),
                "sha256": sha256_file(observation_path),
                "derived_from": [raw_path.relative_to(self.root).as_posix()],
            },
            {
                "layer": "gold",
                "dataset": "holdout_validation",
                "path": validation_path.relative_to(self.root).as_posix(),
                "media_type": "application/json",
                "bytes": validation_path.stat().st_size,
                "records": 1,
                "sha256": sha256_file(validation_path),
                "derived_from": [observation_path.relative_to(self.root).as_posix()],
            },
        ]
        manifest = {
            "schema_version": 1,
            "dataset_version": "v3",
            "run_id": RUN_ID,
            "protocol_version": PROTOCOL,
            "artifacts": artifacts,
            "quality": {"status": "PASS", "error_count": 0, "checks": []},
        }
        manifest_path = self.root / "data" / "manifests" / "v3" / f"{RUN_ID}.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return observation_path

    def test_sql_views_and_gold_cross_check(self):
        self.write_fixture()
        summary = audit_run(RUN_ID, root=self.root, sql_path=SQL_PATH, report_path=self.report)
        self.assertEqual(summary["funnel"]["accepted_observations"], 5)
        self.assertEqual(summary["funnel"]["evaluated"], 3)
        self.assertEqual(summary["primary"]["evaluated_players"], 2)
        self.assertEqual(summary["primary"]["review_candidates"], 0)
        self.assertEqual(summary["deciles"]["1"]["accepted_observations"], 0)
        self.assertEqual(summary["lineage"]["maximum_depth"], 2)
        self.assertEqual(summary["lineage"]["cyclic"], 0)
        self.assertTrue(self.report.exists())

    def test_symlink_escape_and_changed_consumed_bytes_do_not_publish(self):
        source = self.write_fixture()
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "observations.json"
            target.write_bytes(source.read_bytes())
            source.unlink()
            source.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "상대 경로"):
                audit_run(RUN_ID, root=self.root, sql_path=SQL_PATH, report_path=self.report)
            source.unlink()
        self.write_fixture()
        original = LocalFiles.read_checked_bytes

        def replaced(path, expected):
            if path == source:
                path.write_text("[]", encoding="utf-8")
            return original(path, expected)

        with patch.object(LocalFiles, "read_checked_bytes", side_effect=replaced):
            with self.assertRaisesRegex(RuntimeError, "INPUT_CHECKSUM"):
                audit_run(RUN_ID, root=self.root, sql_path=SQL_PATH, report_path=self.report)
        self.assertFalse(self.report.exists())

    def test_dynamic_identifiers_are_a_fixed_allowlist(self):
        with sqlite3.connect(":memory:") as connection:
            with self.assertRaisesRegex(ValueError, "Unknown audit view"):
                _row(connection, "sqlite_master")
            with self.assertRaisesRegex(ValueError, "Unknown audit grouping"):
                _group_rows(connection, "v_map_coverage", "map_name; DROP TABLE artifact")

    def test_invalid_observations_fail_closed(self):
        invalid_status = [dict(row) for row in self.observations]
        invalid_status[0]["status"] = "unknown"
        invalid_status[0]["skip_reason"] = "unknown"
        invalid_player_key = [dict(row) for row in self.observations]
        invalid_player_key[0]["player_key"] = "not-a-key"
        invalid_decile = [dict(row) for row in self.observations]
        invalid_decile[0]["rank_decile"] = 9
        duplicate_id = [dict(row) for row in self.observations] + [
            {**self.observations[0], "match_id": "m6"}
        ]
        for name, rows in (
            ("status", invalid_status),
            ("player_key", invalid_player_key),
            ("rank_decile", invalid_decile),
            ("observation_id", duplicate_id),
        ):
            with self.subTest(name=name):
                self.write_fixture(observations=rows)
                with self.assertRaises(sqlite3.IntegrityError):
                    audit_run(RUN_ID, root=self.root, sql_path=SQL_PATH, report_path=self.report)
                self.assertFalse(self.report.exists())

    def test_gold_mismatch_fails_closed(self):
        self.write_fixture(gold_evaluated=99)
        with self.assertRaisesRegex(RuntimeError, "Gold 교차검증 실패"):
            audit_run(RUN_ID, root=self.root, sql_path=SQL_PATH, report_path=self.report)
        self.assertFalse(self.report.exists())

    def test_null_state_predicate_is_rejected_without_forbidding_valid_nulls(self):
        for field, index in (("eligible_players", 1), ("skip_reason", 2), ("eligible_players", 3)):
            with self.subTest(field=field, index=index):
                rows = [dict(row) for row in self.observations]
                rows[index][field] = None
                self.write_fixture(observations=rows)
                with self.assertRaises(sqlite3.IntegrityError):
                    audit_run(RUN_ID, root=self.root, sql_path=SQL_PATH, report_path=self.report)
                self.assertFalse(self.report.exists())
        self.write_fixture()
        self.assertEqual(
            audit_run(RUN_ID, root=self.root, sql_path=SQL_PATH, report_path=self.report)["funnel"][
                "accepted_observations"
            ],
            5,
        )

    def test_consumed_artifact_checksum_is_verified(self):
        observation_path = self.write_fixture()
        observation_path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "checksum 불일치"):
            audit_run(RUN_ID, root=self.root, sql_path=SQL_PATH, report_path=self.report)
        self.assertFalse(self.report.exists())


if __name__ == "__main__":
    unittest.main()
