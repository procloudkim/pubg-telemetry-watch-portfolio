import json
import math
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src.common import atomic_write_json, sha256_file, write_once
from src.detect import r2_observation
from src.v3 import (
    ApiSession,
    BudgetExhausted,
    candidate_matches,
    clopper_pearson_one_sided,
    cohort_preflight,
    collect_run,
    evaluate_run,
    LEGACY_PROTOCOL_VERSION,
    make_cohort,
    primary_decision,
    prior_exposure,
    PROTOCOL_VERSION,
    run_paths,
    split_players,
    wilson_interval,
)


class V3ProtocolTest(unittest.TestCase):
    def test_decile_assignment_is_complete_holdout_and_deterministic(self):
        leaders = [
            {"id": f"player-{rank}", "attributes": {"rank": rank}} for rank in range(100, 0, -1)
        ]
        first = split_players(leaders, "season")
        second = split_players(list(reversed(leaders)), "season")
        self.assertEqual(first, second)
        for decile in range(1, 11):
            values = [split_name for split_name, group in first.values() if group == decile]
            self.assertEqual(values, ["holdout"] * 10)

    def test_shared_match_has_exactly_one_owner(self):
        cohort = {
            "players": [
                {
                    "player_key": "a",
                    "rank": 1,
                    "rank_decile": 1,
                    "split": "holdout",
                    "recent_match_ids": ["shared", "only-a"],
                },
                {
                    "player_key": "b",
                    "rank": 11,
                    "rank_decile": 2,
                    "split": "holdout",
                    "recent_match_ids": ["shared", "only-b"],
                },
            ]
        }
        rows = candidate_matches(cohort)
        self.assertEqual({row["match_id"] for row in rows}, {"shared", "only-a", "only-b"})
        self.assertEqual(sum(row["match_id"] == "shared" for row in rows), 1)

    def test_preflight_blocks_cohort_attrition_before_api_session(self):
        players = [
            {
                "player_key": f"p{rank}",
                "rank": rank,
                "rank_decile": (rank - 1) // 10 + 1,
                "split": "holdout",
                "prior_excluded_references": 0,
                "recent_match_ids": [f"m{rank}-1", f"m{rank}-2"],
            }
            for rank in range(1, 101)
        ]
        valid = {
            "protocol_version": "v3-r2-top100-2",
            "players": players,
            "prior_excluded_references": 0,
        }
        self.assertEqual(cohort_preflight(valid)["status"], "PASS")
        broken = {
            **valid,
            "players": [
                {**row, "recent_match_ids": []} if row["rank"] <= 10 else row for row in players
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch("src.cli.research_composition.ROOT", root),
                patch("src.application.research.Research.api_session") as session,
            ):
                atomic_write_json(root / "data/silver" / "v3" / "run" / "cohort.json", broken)
                with self.assertRaises(SystemExit):
                    collect_run("run", "session", 60)
                session.assert_not_called()
                report = json.loads(
                    (root / "data/silver" / "v3" / "run" / "preflight.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(report["by_rank_decile"]["1"]["candidate_owner_players"], 0)

    def test_protocol3_excludes_prior_v3_candidates_but_legacy_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = {
                "protocol_version": LEGACY_PROTOCOL_VERSION,
                "players": [
                    {
                        "player_key": "old",
                        "rank": 1,
                        "rank_decile": 1,
                        "split": "holdout",
                        "recent_match_ids": ["old-match"],
                    }
                ],
            }
            current = {
                "protocol_version": PROTOCOL_VERSION,
                "players": [
                    {
                        "player_key": "current",
                        "rank": 1,
                        "rank_decile": 1,
                        "split": "holdout",
                        "recent_match_ids": ["current-match"],
                    }
                ],
            }
            atomic_write_json(root / "data/manifest.json", [{"match_id": "v1-match"}])
            atomic_write_json(root / "data/silver/v3/old/cohort.json", old)
            atomic_write_json(root / "data/silver/v3/current/cohort.json", current)
            with patch("src.cli.research_composition.ROOT", root):
                exposed, hashes, paths = prior_exposure(PROTOCOL_VERSION, "current")
                legacy, _, _ = prior_exposure(LEGACY_PROTOCOL_VERSION, "current")
            self.assertEqual(exposed, {"v1-match", "old-match"})
            self.assertEqual(legacy, {"v1-match"})
            self.assertIn("v3:old", hashes)
            self.assertNotIn(root / "data/silver/v3/current/cohort.json", paths)

    def test_predeclared_binomial_bound(self):
        lower, upper = clopper_pearson_one_sided(0, 59)
        self.assertEqual(lower, 0.0)
        self.assertAlmostEqual(upper, 1 - math.pow(0.05, 1 / 59), places=10)
        self.assertLess(upper, 0.05)
        self.assertEqual(primary_decision(0, 58)["status"], "INSUFFICIENT_SAMPLE")
        self.assertEqual(primary_decision(0, 59)["status"], "CRITERION_SUPPORTED")

    def test_wilson_zero_event_reference(self):
        lower, upper = wilson_interval(0, 150)
        self.assertEqual(lower, 0.0)
        self.assertAlmostEqual(upper, 0.02497, places=4)

    def test_r2_statuses_are_exclusive(self):
        low = {"target": {"account_id": "id", "attacks": 29, "damage_events": 29}}
        self.assertEqual(r2_observation(low, account_id="id")["status"], "target_below_min_attacks")
        small_pool = {
            f"p{i}": {"account_id": str(i), "attacks": 30, "damage_events": i} for i in range(7)
        }
        self.assertEqual(r2_observation(small_pool, account_id="0")["status"], "match_pool_below_8")
        structural_pool = {
            f"p{i}": {"account_id": str(i), "attacks": 30, "damage_events": i} for i in range(10)
        }
        self.assertEqual(
            r2_observation(structural_pool, account_id="0")["status"],
            "match_pool_below_signal_capable",
        )
        evaluated = {
            f"p{i}": {"account_id": str(i), "attacks": 100, "damage_events": 100 if i == 0 else 10}
            for i in range(11)
        }
        result = r2_observation(evaluated, account_id="0")
        self.assertEqual(result["status"], "evaluated")
        self.assertTrue(result["review_candidate"])


class BronzeWriteOnceTest(unittest.TestCase):
    def test_write_once_reuses_equal_bytes_and_rejects_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.json"
            write_once(path, b"{}")
            write_once(path, b"{}")
            with self.assertRaises(RuntimeError):
                write_once(path, b"[]")

    def test_api_budget_is_shared_across_run_ledgers(self):
        class Response:
            status_code = 200
            content = b"{}"

            def raise_for_status(self):
                return None

            def json(self):
                return {}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            global_ledger = root / "session.jsonl"
            with (
                patch("src.adapters.http.api_key", return_value="secret"),
                patch("src.adapters.http.requests.get", return_value=Response()),
            ):
                first = ApiSession(global_ledger, root / "run-a.jsonl", "same-session", 1)
                first.get("/one", root / "one.json")
                second = ApiSession(global_ledger, root / "run-b.jsonl", "same-session", 1)
                with self.assertRaises(BudgetExhausted):
                    second.get("/two", root / "two.json")
            self.assertNotIn("secret", global_ledger.read_text(encoding="utf-8"))

    def test_api_session_waits_from_last_global_request(self):
        class Response:
            status_code = 200
            content = b"{}"

            def raise_for_status(self):
                return None

            def json(self):
                return {}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            global_ledger = root / "session.jsonl"
            global_ledger.write_text(
                json.dumps(
                    {
                        "session_id": "earlier",
                        "cache_hit": False,
                        "requested_at": datetime.now(timezone.utc).isoformat(
                            timespec="microseconds"
                        ),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            requested = datetime.fromisoformat(
                json.loads(global_ledger.read_text(encoding="utf-8"))["requested_at"]
            )
            with (
                patch("src.adapters.http.api_key", return_value="secret"),
                patch("src.adapters.http.requests.get", return_value=Response()),
                patch("src.adapters.clock.datetime") as clock,
                patch("src.adapters.clock.time.sleep") as sleeper,
            ):
                clock.fromisoformat.side_effect = datetime.fromisoformat
                clock.now.side_effect = [
                    requested,
                    requested + timedelta(seconds=7),
                    requested + timedelta(seconds=7),
                    requested + timedelta(seconds=7),
                ]
                ApiSession(global_ledger, root / "run.jsonl", "new-session", 1).get(
                    "/one", root / "one.json"
                )
            self.assertEqual(sleeper.call_args.args[0], 7)

    def test_abrupt_exit_reserves_budget_and_recovers_run_mirror(self):
        script = """
import os, sys
from pathlib import Path
from unittest.mock import patch
import src.v3 as v3
from src.adapters import files, http
root, phase = Path(sys.argv[1]), sys.argv[2]
original_append, original_write = files.LocalFiles.append_ledger, files.write_once
original_check = http.HttpReply.raise_for_status
def append(self, path, row):
    if path == root / 'api-ledger.jsonl' and row['phase'] == phase:
        os._exit(37)
    original_append(self, path, row)
def write(path, body):
    original_write(path, body)
    if phase == 'cache':
        os._exit(37)
def check(self):
    if phase == 'response':
        os._exit(37)
    original_check(self)
class Response:
    status_code, content = 200, b'{}'
    def raise_for_status(self):
        if phase == 'response':
            os._exit(37)
    def json(self):
        return {}
with patch.object(http, 'api_key', return_value='test-placeholder'), \\
     patch.object(http.requests, 'get', return_value=Response()), \\
     patch.object(files.LocalFiles, 'append_ledger', new=append), patch.object(http.HttpReply, 'raise_for_status', new=check), \\
     patch.object(files, 'write_once', side_effect=write):
    v3.ApiSession(root / 'global.jsonl', root / 'api-ledger.jsonl', 'same', 1).get('/one', root / 'cache.json')
"""
        from src.v3 import _ledger_requests, _read_ledger, api_ledger_stats

        for phase in ("reserved", "response", "cache", "completed"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                child = subprocess.run(
                    [sys.executable, "-c", script, str(root), phase],
                    capture_output=True,
                    timeout=20,
                )
                self.assertEqual(child.returncode, 37, child.stderr.decode())
                client = ApiSession(root / "global.jsonl", root / "api-ledger.jsonl", "same", 1)
                self.assertEqual(client.used, 1)
                with patch("src.adapters.http.requests.get") as transport:
                    with self.assertRaises(BudgetExhausted):
                        client.get("/two", root / "other.json")
                    transport.assert_not_called()
                self.assertEqual(
                    _ledger_requests(_read_ledger(root / "global.jsonl")),
                    _ledger_requests(_read_ledger(root / "api-ledger.jsonl")),
                )
                self.assertEqual(api_ledger_stats(root)["network_calls"], 1)

    def test_damaged_ledger_and_reservation_write_error_block_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "global.jsonl"
            ledger.write_text('{"session_id":', encoding="utf-8")
            with patch("src.adapters.http.requests.get") as transport:
                with self.assertRaises(ValueError):
                    ApiSession(ledger, root / "api-ledger.jsonl", "same", 1)
                transport.assert_not_called()
            ledger.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                ApiSession(ledger, root / "api-ledger.jsonl", "same", 1)
            ledger.unlink()
            client = ApiSession(ledger, root / "api-ledger.jsonl", "same", 1)
            with (
                patch("src.adapters.http.api_key", return_value="test-placeholder"),
                patch("src.adapters.files.LocalFiles.append_ledger", side_effect=OSError),
                patch("src.adapters.http.requests.get") as transport,
            ):
                with self.assertRaises(OSError):
                    client.get("/one", root / "cache.json")
                transport.assert_not_called()


class V3OfflinePipelineTest(unittest.TestCase):
    def test_evaluate_publishes_only_pseudonymous_intermediate_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = root / "data/manifests"
            patches = [patch("src.cli.research_composition.ROOT", root)]
            for active in patches:
                active.start()
            try:
                bronze, silver, _ = run_paths("synthetic")
                leaders = [
                    {
                        "type": "player",
                        "id": f"account-{rank}",
                        "attributes": {"rank": rank, "name": f"name-{rank}"},
                    }
                    for rank in range(1, 101)
                ]
                atomic_write_json(bronze / "api" / "seasons.json", {"data": []})
                atomic_write_json(bronze / "api" / "leaderboard.json", {"included": leaders})
                payloads, player_paths = [], []
                for batch in range(10):
                    rows = [
                        {
                            "id": f"account-{rank}",
                            "relationships": {"matches": {"data": [{"id": f"match-{rank}"}]}},
                        }
                        for rank in range(batch * 10 + 1, batch * 10 + 11)
                    ]
                    payload, path = (
                        {"data": rows},
                        bronze / "api" / "players" / f"{batch + 1:02d}.json",
                    )
                    atomic_write_json(path, payload)
                    payloads.append(payload)
                    player_paths.append(path)
                prior_path = root / "data" / "manifest.json"
                atomic_write_json(prior_path, [{"match_id": "match-1"}])
                source_hashes = {
                    "seasons": sha256_file(bronze / "api" / "seasons.json"),
                    "leaderboard": sha256_file(bronze / "api" / "leaderboard.json"),
                    "player_batches": [sha256_file(path) for path in player_paths],
                    "prior_selections": {"v1": sha256_file(prior_path)},
                }
                cohort = make_cohort(
                    leaders,
                    payloads,
                    "season",
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:01:00+00:00",
                    source_hashes,
                    {"match-1"},
                )
                atomic_write_json(silver / "cohort.json", cohort)
                self.assertEqual(cohort["prior_excluded_references"], 1)
                self.assertNotIn("match-1", {row["match_id"] for row in candidate_matches(cohort)})
                for rank in range(1, 101):
                    match_id = f"match-{rank}"
                    atomic_write_json(
                        bronze / "api" / "matches" / f"{match_id}.json",
                        {
                            "data": {
                                "id": match_id,
                                "attributes": {"gameMode": "squad-fpp", "mapName": "Map"},
                            }
                        },
                    )
                    actors = [(f"name-{rank}", f"account-{rank}")] + [
                        (f"other-{rank}-{index}", f"other-account-{rank}-{index}")
                        for index in range(10)
                    ]
                    events = [
                        {
                            "_T": "LogPlayerAttack",
                            "attackId": attack_id,
                            "attacker": {"name": name, "accountId": account},
                        }
                        for name, account in actors
                        for attack_id in range(30)
                    ]
                    events += [
                        {
                            "_T": "LogPlayerTakeDamage",
                            "attacker": {"name": name, "accountId": account},
                            "attackId": attack_id,
                            "damage": 1,
                        }
                        for name, account in actors
                        for attack_id in range(3)
                    ]
                    write_once(
                        bronze / "telemetry" / f"{match_id}.json", json.dumps(events).encode()
                    )
                result = evaluate_run("synthetic")
                self.assertEqual(result["experiment_status"], "INTERMEDIATE")
                self.assertEqual(result["primary"]["evaluated_players"], 99)
                self.assertEqual(result["secondary"]["evaluated"], 99)
                self.assertEqual(
                    json.loads((manifests / "v3" / "synthetic.json").read_text(encoding="utf-8"))[
                        "quality"
                    ]["status"],
                    "PASS",
                )
                silver_text = (silver / "observations.json").read_text(encoding="utf-8")
                self.assertNotIn("name-1", silver_text)
                self.assertNotIn("account-1", silver_text)
            finally:
                for active in reversed(patches):
                    active.stop()


if __name__ == "__main__":
    unittest.main()
