import json
import tempfile
import unittest
from pathlib import Path

from src.graph_spike import analyze_run, write_report
from src.v3 import digest


class GraphSpikeTest(unittest.TestCase):
    def fixture(self, root, *, mode="squad-fpp", unresolved=False, cyclic=False):
        run_id = "synthetic-run"
        bronze = root / "data/bronze/v3" / run_id
        silver = root / "data/silver/v3" / run_id
        manifest_path = root / "data/manifests/v3" / f"{run_id}.json"
        match_dir = bronze / "api/matches"
        parsed_dir = silver / "parsed"
        match_dir.mkdir(parents=True)
        parsed_dir.mkdir(parents=True)
        manifest_path.parent.mkdir(parents=True)

        protocol, season = "protocol", "season"
        player_ids = ("account.a", "account.b")
        player_keys = [digest(protocol, season, value)[:24] for value in player_ids]
        (silver / "cohort.json").write_text(
            json.dumps(
                {
                    "protocol_version": protocol,
                    "season_id": season,
                    "players": [{"player_key": key} for key in player_keys],
                }
            ),
            encoding="utf-8",
        )
        observations = [
            {
                "observation_id": f"observation-{index}",
                "match_id": f"match-{index}",
                "player_key": player_keys[0],
            }
            for index in (1, 2)
        ]
        (silver / "observations.json").write_text(json.dumps(observations), encoding="utf-8")

        for index in (1, 2):
            participants = [
                {
                    "type": "participant",
                    "id": f"participant-{letter}",
                    "attributes": {"stats": {"playerId": player_id, "name": f"name-{letter}"}},
                }
                for letter, player_id in zip(("a", "b"), player_ids)
            ]
            refs = [
                {"id": "participant-a"},
                {"id": "missing" if unresolved and index == 1 else "participant-b"},
            ]
            roster = {
                "type": "roster",
                "id": f"roster-{index}",
                "attributes": {"stats": {"teamId": 1}},
                "relationships": {"participants": {"data": refs}},
            }
            payload = {
                "data": {"id": f"match-{index}", "attributes": {"gameMode": mode}},
                "included": participants + [roster],
            }
            (match_dir / f"match-{index}.json").write_text(json.dumps(payload), encoding="utf-8")
            (parsed_dir / f"match-{index}.json").write_text(
                json.dumps({"players": {"different-key": {}}}), encoding="utf-8"
            )

        bronze_one = "data/bronze/v3/synthetic-run/api/matches/match-1.json"
        bronze_two = "data/bronze/v3/synthetic-run/api/matches/match-2.json"
        silver_observations = "data/silver/v3/synthetic-run/observations.json"
        gold = "data/gold/v3/synthetic-run/validation.json"
        artifacts = [
            {"path": bronze_one, "layer": "bronze", "derived_from": [gold] if cyclic else []},
            {"path": bronze_two, "layer": "bronze", "derived_from": []},
            {
                "path": silver_observations,
                "layer": "silver",
                "derived_from": [bronze_one, bronze_two],
            },
            {"path": gold, "layer": "gold", "derived_from": [silver_observations]},
        ]
        manifest_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "protocol_version": protocol,
                    "quality": {"status": "PASS"},
                    "artifacts": artifacts,
                }
            ),
            encoding="utf-8",
        )
        return run_id, bronze, silver, manifest_path

    def test_projection_counts_queries_and_privacy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            summary, raw_tokens = analyze_run(*args)
            report = write_report(summary, raw_tokens, root / "report.md")
            self.assertEqual(summary["decision"], "FEASIBLE_FOR_NEO4J_REVIEW")
            self.assertEqual(summary["relationship_query"]["repeated_at_least_2"], 1)
            self.assertEqual(summary["relationship_query"]["maximum_repeat"], 2)
            self.assertEqual(summary["key_query"]["observation_rows_in_own_match"], 2)
            self.assertEqual(summary["key_query"]["parsed_direct_rows"], 0)
            self.assertEqual(
                summary["graph"]["nodes"],
                {"artifact": 4, "match": 2, "observation": 2, "player": 2, "team": 2},
            )
            self.assertEqual(summary["relationship_query"]["players_by_key_type"], {"account": 2})
            self.assertEqual(
                summary["relationship_query"]["repeated_by_key_type"], {"account+account": 1}
            )
            for token in ("account.a", "account.b", "name-a", "name-b"):
                self.assertNotIn(token, report)

    def test_projection_hash_is_input_order_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            first, _ = analyze_run(*args)
            for path in (args[1] / "api/matches").glob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["included"].reverse()
                roster = next(row for row in payload["included"] if row["type"] == "roster")
                roster["relationships"]["participants"]["data"].reverse()
                path.write_text(json.dumps(payload), encoding="utf-8")
            second, _ = analyze_run(*args)
            self.assertEqual(
                first["graph"]["projection_sha256"], second["graph"]["projection_sha256"]
            )

    def test_invalid_relationship_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                analyze_run(*self.fixture(Path(directory), unresolved=True))

    def test_mode_and_lineage_cycle_stop_adoption(self):
        for options in ({"mode": "duo-fpp"}, {"cyclic": True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                summary, raw_tokens = analyze_run(*self.fixture(root, **options))
                write_report(summary, raw_tokens, root / "report.md")
                self.assertEqual(summary["decision"], "STOP")


if __name__ == "__main__":
    unittest.main()
