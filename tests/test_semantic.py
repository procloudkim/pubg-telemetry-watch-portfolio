import gzip
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from rdflib import Graph, Literal, URIRef

from src.common import sha256_file
from src.parse import LEGACY_RULE_PROTOCOL_VERSION, RULE_PROTOCOL_VERSION
from src.semantic import SemanticConformanceError, _canonical_ntriples, build_sidecar
from src.v3 import LEGACY_PROTOCOL_VERSION, PROTOCOL_VERSION, digest


REPOSITORY = Path(__file__).resolve().parents[1]
RUN_ID = "semantic-test-run"


class SemanticSidecarTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        shutil.copytree(REPOSITORY / "docs/ontology", self.root / "docs/ontology")
        (self.root / "sql").mkdir()
        shutil.copy2(REPOSITORY / "sql/v3_audit.sql", self.root / "sql/v3_audit.sql")

    def tearDown(self):
        self.temporary.cleanup()

    def write_json(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def artifact(self, path, layer, dataset, derived_from=()):
        relative = path.relative_to(self.root).as_posix()
        value = json.loads(path.read_text(encoding="utf-8"))
        records = len(value) if isinstance(value, list) else 1
        return {
            "layer": layer,
            "dataset": dataset,
            "path": relative,
            "media_type": "application/json",
            "bytes": path.stat().st_size,
            "records": records,
            "sha256": sha256_file(path),
            "derived_from": list(derived_from),
        }

    def fixture(self, *, legacy=False):
        experiment = LEGACY_PROTOCOL_VERSION if legacy else PROTOCOL_VERSION
        rule = LEGACY_RULE_PROTOCOL_VERSION if legacy else RULE_PROTOCOL_VERSION
        season = "season-test"
        account_ids = ("account.alpha", "account.bravo")
        names = ("AlphaPrivate", "BravoPrivate")
        player_keys = [digest(experiment, season, value)[:24] for value in account_ids]
        protocol = {"protocol_version": experiment}
        if not legacy:
            protocol["rule_protocol_version"] = rule
        protocol_path = self.write_json(f"data/bronze/v3/{RUN_ID}/protocol.json", protocol)

        match_paths, parsed_paths = [], []
        for index in (1, 2):
            match_id = f"match-{index}"
            participants = [
                {
                    "type": "participant",
                    "id": f"participant-{position}",
                    "attributes": {"stats": {"playerId": account_id, "name": name}},
                }
                for position, (account_id, name) in enumerate(zip(account_ids, names), 1)
            ]
            roster = {
                "type": "roster",
                "id": f"roster-{index}",
                "attributes": {"stats": {"teamId": 1}},
                "relationships": {
                    "participants": {"data": [{"id": "participant-1"}, {"id": "participant-2"}]}
                },
            }
            match_paths.append(
                self.write_json(
                    f"data/bronze/v3/{RUN_ID}/api/matches/{match_id}.json",
                    {
                        "data": {
                            "id": match_id,
                            "attributes": {"gameMode": "squad-fpp", "mapName": "Baltic_Main"},
                        },
                        "included": participants + [roster],
                    },
                )
            )
            parsed_paths.append(
                self.write_json(
                    f"data/silver/v3/{RUN_ID}/parsed/{match_id}.json",
                    {"players": {"different-key": {}}},
                )
            )

        cohort_path = self.write_json(
            f"data/silver/v3/{RUN_ID}/cohort.json",
            {
                "protocol_version": experiment,
                "season_id": season,
                "players": [{"player_key": key} for key in player_keys],
            },
        )
        observations = []
        for index, recent_index, candidate, local_z in ((1, 2, True, 4.0), (2, 1, False, 1.0)):
            row = {
                "observation_id": str(index) * 24,
                "match_id": f"match-{index}",
                "player_key": player_keys[0],
                "rank": 11,
                "rank_decile": 2,
                "split": "holdout",
                "recent_index": recent_index,
                "season_id": season,
                "mode": "squad-fpp",
                "map": "Baltic_Main",
                "attacks": 40,
                "damage_events": 20,
                "ratio": 0.5,
                "review_candidate": candidate,
                "minimum_signal_pool": 11,
                "status": "evaluated",
                "eligible_players": 20,
                "match_mean": 0.4,
                "match_sd": 0.1,
                "local_z": local_z,
                "skip_reason": None,
            }
            if not legacy:
                row["rule_protocol_version"] = rule
            observations.append(row)
        observation_path = self.write_json(
            f"data/silver/v3/{RUN_ID}/observations.json", observations
        )
        gold = {
            "run_id": RUN_ID,
            "protocol_version": experiment,
            "experiment_status": "INTERMEDIATE",
            "denominators": {
                "accepted_observations": 2,
                "evaluated": 2,
                "target_below_min_attacks": 0,
                "match_pool_below_8": 0,
                "match_pool_below_signal_capable": 0,
            },
            "primary": {"evaluated_players": 1, "review_candidates": 0},
            "secondary": {"evaluated": 2, "review_candidates": 1},
            "by_map": {"Baltic_Main": {"evaluated": 2, "review_candidates": 1}},
            "by_rank_decile": {"2": {"evaluated": 2, "review_candidates": 1}},
        }
        if not legacy:
            gold["rule_protocol_version"] = rule
        gold_path = self.write_json(f"data/gold/v3/{RUN_ID}/validation.json", gold)

        artifacts = [self.artifact(protocol_path, "bronze", RUN_ID)]
        for match_path in match_paths:
            artifacts.append(self.artifact(match_path, "bronze", "matches"))
        for parsed_path, match_path in zip(parsed_paths, match_paths):
            artifacts.append(
                self.artifact(
                    parsed_path,
                    "silver",
                    "parsed_players",
                    (match_path.relative_to(self.root).as_posix(),),
                )
            )
        artifacts.append(
            self.artifact(
                cohort_path,
                "silver",
                "frozen_cohort",
                (protocol_path.relative_to(self.root).as_posix(),),
            )
        )
        artifacts.append(
            self.artifact(
                observation_path,
                "silver",
                "r2_observations",
                tuple(path.relative_to(self.root).as_posix() for path in parsed_paths),
            )
        )
        artifacts.append(
            self.artifact(
                gold_path,
                "gold",
                "holdout_validation",
                (
                    observation_path.relative_to(self.root).as_posix(),
                    cohort_path.relative_to(self.root).as_posix(),
                ),
            )
        )
        manifest_path = self.write_json(
            f"data/manifests/v3/{RUN_ID}.json",
            {
                "schema_version": 1,
                "dataset_version": "v3",
                "run_id": RUN_ID,
                "protocol_version": experiment,
                "artifacts": artifacts,
                "quality": {"status": "PASS", "error_count": 0, "checks": []},
            },
        )
        return manifest_path, account_ids + names

    def test_valid_sidecar_is_deterministic_and_private(self):
        base_manifest, raw_tokens = self.fixture()
        base_hash = sha256_file(base_manifest)
        stale_failure = self.write_json(
            f"reports/semantic-validation-{RUN_ID}.json", {"conforms": False}
        )
        first = build_sidecar(RUN_ID, root=self.root)
        second = build_sidecar(RUN_ID, root=self.root)
        self.assertEqual(first, second)
        self.assertFalse(stale_failure.exists())
        self.assertEqual(sha256_file(base_manifest), base_hash)
        self.assertEqual(first["quality"]["status"], "PASS")
        self.assertEqual(first["rule_protocol_version"], RULE_PROTOCOL_VERSION)

        graph_path = self.root / f"data/gold/v3/{RUN_ID}/semantic.nt.gz"
        validation_path = self.root / f"data/gold/v3/{RUN_ID}/semantic-validation.json"
        body = gzip.decompress(graph_path.read_bytes())
        graph = Graph().parse(data=body.decode("utf-8"), format="nt")
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        self.assertEqual(len(graph), validation["graph"]["triples"])
        self.assertEqual(hashlib.sha256(body).hexdigest(), validation["graph"]["ntriples_sha256"])
        self.assertTrue(
            all(row["status"] == "PASS" for row in validation["competency_queries"].values())
        )
        for token in raw_tokens:
            self.assertNotIn(token.encode(), body)

    def test_canonical_ntriples_ignores_insertion_order(self):
        triples = [
            (URIRef("https://example.test/b"), URIRef("https://example.test/p"), Literal("2")),
            (URIRef("https://example.test/a"), URIRef("https://example.test/p"), Literal("1")),
        ]
        forward, reverse = Graph(), Graph()
        for triple in triples:
            forward.add(triple)
        for triple in reversed(triples):
            reverse.add(triple)
        self.assertEqual(_canonical_ntriples(forward), _canonical_ntriples(reverse))

    def test_legacy_run_gets_only_the_declared_fallback(self):
        self.fixture(legacy=True)
        manifest = build_sidecar(RUN_ID, root=self.root)
        self.assertEqual(manifest["protocol_version"], LEGACY_PROTOCOL_VERSION)
        self.assertEqual(manifest["rule_protocol_version"], LEGACY_RULE_PROTOCOL_VERSION)

    def test_checksum_change_stops_before_publish(self):
        self.fixture()
        observation_path = self.root / f"data/silver/v3/{RUN_ID}/observations.json"
        observation_path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "(?:byte|checksum) 불일치"):
            build_sidecar(RUN_ID, root=self.root)
        self.assertFalse((self.root / f"data/gold/v3/{RUN_ID}/semantic.nt.gz").exists())
        self.assertFalse((self.root / f"data/manifests/semantic/v3/{RUN_ID}.json").exists())

    def test_shacl_failure_writes_diagnostic_without_publish(self):
        self.fixture()
        shapes = self.root / "docs/ontology/pubg-watch.shacl.ttl"
        shapes.write_text(
            shapes.read_text(encoding="utf-8").replace(
                'sh:hasValue "1.0.0"^^xsd:string',
                'sh:hasValue "9.0.0"^^xsd:string',
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(SemanticConformanceError, "SHACL"):
            build_sidecar(RUN_ID, root=self.root)
        diagnostic = self.root / f"reports/semantic-validation-{RUN_ID}.json"
        self.assertFalse(json.loads(diagnostic.read_text(encoding="utf-8"))["conforms"])
        self.assertFalse((self.root / f"data/gold/v3/{RUN_ID}/semantic.nt.gz").exists())
        self.assertFalse((self.root / f"data/manifests/semantic/v3/{RUN_ID}.json").exists())

    def test_oracle_failures_replace_diagnostic_without_publishing_or_changing_sources(self):
        for stage, dataset in (("graph", "frozen_cohort"), ("sql", "holdout_validation")):
            with self.subTest(stage=stage):
                manifest_path, raw_tokens = self.fixture()
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                artifact = next(row for row in manifest["artifacts"] if row["dataset"] == dataset)
                source = self.root / artifact["path"]
                value = json.loads(source.read_text(encoding="utf-8"))
                if stage == "graph":
                    value["players"] = []
                else:
                    value["primary"]["review_candidates"] = 1
                self.write_json(artifact["path"], value)
                artifact.update(bytes=source.stat().st_size, sha256=sha256_file(source))
                self.write_json(manifest_path.relative_to(self.root), manifest)
                sources = {path: sha256_file(path) for path in (self.root / "data").rglob("*.json")}
                diagnostic = self.write_json(
                    f"reports/semantic-validation-{RUN_ID}.json", {"stale": True}
                )
                with self.assertRaisesRegex(SemanticConformanceError, "graph DQ|SQL과 Gold"):
                    build_sidecar(RUN_ID, root=self.root)
                payload = json.loads(diagnostic.read_text(encoding="utf-8"))
                self.assertFalse(payload["conforms"])
                self.assertEqual(payload["stage"], stage)
                self.assertEqual(payload["run_id"], RUN_ID)
                self.assertNotIn("stale", payload)
                for token in raw_tokens:
                    self.assertNotIn(token, diagnostic.read_text(encoding="utf-8"))
                self.assertFalse((self.root / f"data/gold/v3/{RUN_ID}/semantic.nt.gz").exists())
                self.assertFalse((self.root / f"data/manifests/semantic/v3/{RUN_ID}.json").exists())
                self.assertEqual({path: sha256_file(path) for path in sources}, sources)


if __name__ == "__main__":
    unittest.main()
