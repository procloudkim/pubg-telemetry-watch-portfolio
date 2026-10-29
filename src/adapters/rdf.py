"""Local RDF, SHACL and SPARQL engine; returns plain verified result data."""

import gzip
import hashlib
import io
import json
import math
import re
import sys
from collections import Counter
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from urllib.parse import quote
from pyshacl import validate as shacl_validate
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import PROV, XSD
from src.domain.errors import SemanticConformanceError
from src.domain.semantic import (
    ONTOLOGY_VERSION,
    PROJECTOR_VERSION,
    ONTOLOGY_IRI,
    QUERY_FILES,
    _expected_queries,
)
from src.domain.graph import _check
from src.domain.serialization import digest
from .files import read_checked_bytes

PTW = Namespace(ONTOLOGY_IRI + "#")
INSTANCE = "https://procloudkim.github.io/pubg-telemetry-watch/id/"
PLAYER_KEY = re.compile(r"[0-9a-f]{24}\Z")
STATUS_IRIS = {
    "evaluated": PTW.statusEvaluated,
    "target_below_min_attacks": PTW.statusTargetBelowMinAttacks,
    "match_pool_below_8": PTW.statusMatchPoolBelow8,
    "match_pool_below_signal_capable": PTW.statusMatchPoolBelowSignalCapable,
}


def _load_json(path: Path, expected_type, expected_sha256):
    value = json.loads(read_checked_bytes(path, expected_sha256))
    if not isinstance(value, expected_type):
        raise ValueError(f"JSON 최상위 형식 오류: {path.name}")
    return value


def _load_contract(root: Path) -> dict:
    contract = root / "docs/ontology"
    ontology_path = contract / "pubg-watch.ttl"
    release_path = contract / "releases/1.0.0/pubg-watch.ttl"
    shapes_path = contract / "pubg-watch.shacl.ttl"
    if ontology_path.read_bytes() != release_path.read_bytes():
        raise RuntimeError("stable ontology와 version ontology byte 불일치")
    ontology = Graph().parse(ontology_path, format="turtle")
    shapes = Graph().parse(shapes_path, format="turtle")
    query_dir = contract / "queries"
    paths = {path.name: path for path in query_dir.glob("*.rq")}
    if set(paths) != set(QUERY_FILES.values()):
        raise RuntimeError("competency query 파일 집합 불일치")
    queries = {}
    forbidden = re.compile(
        r"\b(SERVICE|LOAD|INSERT|DELETE|CLEAR|CREATE|DROP|MOVE|COPY|ADD)\b", re.I
    )
    for query_id, filename in QUERY_FILES.items():
        text = paths[filename].read_text(encoding="utf-8")
        if forbidden.search(text):
            raise RuntimeError(f"원격 또는 변경 SPARQL 금지: {filename}")
        queries[query_id] = {"path": paths[filename], "text": text}
    return {
        "ontology": ontology,
        "ontology_path": ontology_path,
        "release_path": release_path,
        "shapes": shapes,
        "shapes_path": shapes_path,
        "queries": queries,
    }


def _iri(kind: str, value) -> URIRef:
    return URIRef(f"{INSTANCE}{kind}/{quote(str(value), safe='')}")


def _artifact_iri(path: str, sha256: str | None) -> URIRef:
    key = hashlib.sha256(f"{path}\0{sha256 or ''}".encode()).hexdigest()
    return _iri("artifact", key)


def _string(value, label: str) -> Literal:
    if not isinstance(value, str) or not value:
        raise ValueError(f"문자열 필드 오류: {label}")
    return Literal(value, datatype=XSD.string)


def _integer(value, label: str, *, positive=False) -> Literal:
    if not isinstance(value, int) or isinstance(value, bool) or value < int(positive):
        raise ValueError(f"정수 필드 오류: {label}")
    return Literal(value, datatype=XSD.positiveInteger if positive else XSD.nonNegativeInteger)


def _decimal(value, label: str) -> Literal:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"decimal 필드 오류: {label}")
    return Literal(format(Decimal(str(value)), "f"), datatype=XSD.decimal, normalize=False)


def _boolean(value, label: str) -> Literal:
    if not isinstance(value, bool):
        raise ValueError(f"boolean 필드 오류: {label}")
    return Literal(value, datatype=XSD.boolean)


def _project_graph(sources: dict, experiment: str, rule: str, season: str):
    graph = Graph()
    graph.bind("prov", PROV)
    graph.bind("ptw", PTW)
    run_id = sources["run_id"]
    run_node = _iri("run", run_id)
    experiment_node = _iri("experiment-protocol", experiment)
    rule_node = _iri("rule-protocol", rule)
    graph.add((experiment_node, RDF.type, PTW.ExperimentProtocol))
    graph.add((experiment_node, PTW.protocolVersion, _string(experiment, "protocol_version")))
    graph.add((rule_node, RDF.type, PTW.RuleProtocol))
    graph.add((rule_node, PTW.ruleProtocolVersion, _string(rule, "rule_protocol_version")))
    graph.add((run_node, RDF.type, PTW.PipelineRun))
    graph.add((run_node, PTW.runId, _string(run_id, "run_id")))
    graph.add((run_node, PTW.ontologyVersion, _string(ONTOLOGY_VERSION, "ontology_version")))
    graph.add((run_node, PTW.governedByExperiment, experiment_node))
    graph.add((run_node, PTW.evaluatedByRule, rule_node))

    artifacts = sources["manifest"]["artifacts"]
    managed = {row["path"]: _artifact_iri(row["path"], row["sha256"]) for row in artifacts}
    referenced = {path for row in artifacts for path in row["derived_from"]}
    artifact_nodes = {**managed}
    for path in sorted(referenced - set(managed)):
        artifact_nodes[path] = _artifact_iri(path, None)
    for row in artifacts:
        node = managed[row["path"]]
        graph.add((node, RDF.type, PTW.DataArtifact))
        graph.add((node, PTW.artifactPath, _string(row["path"], "artifact.path")))
        graph.add((node, PTW.managedArtifact, Literal(True, datatype=XSD.boolean)))
        graph.add((node, PTW.layer, _string(row["layer"], "artifact.layer")))
        graph.add((node, PTW.dataset, _string(row["dataset"], "artifact.dataset")))
        graph.add((node, PTW.mediaType, _string(row["media_type"], "artifact.media_type")))
        graph.add((node, PTW.byteSize, _integer(row["bytes"], "artifact.bytes")))
        graph.add((node, PTW.recordCount, _integer(row["records"], "artifact.records")))
        graph.add((node, PTW.sha256, _string(row["sha256"], "artifact.sha256")))
        graph.add((node, PROV.wasGeneratedBy, run_node))
        if not row["derived_from"]:
            graph.add((run_node, PROV.used, node))
    for path in sorted(referenced - set(managed)):
        node = artifact_nodes[path]
        graph.add((node, RDF.type, PTW.DataArtifact))
        graph.add((node, PTW.artifactPath, _string(path, "external artifact.path")))
        graph.add((node, PTW.managedArtifact, Literal(False, datatype=XSD.boolean)))
        graph.add((run_node, PROV.used, node))
    for row in artifacts:
        for source in row["derived_from"]:
            graph.add((managed[row["path"]], PROV.wasDerivedFrom, artifact_nodes[source]))

    observations = sources["observations"]
    cohort_players = sources["cohort"].get("players")
    if not isinstance(cohort_players, list):
        raise ValueError("cohort players 형식 오류")
    cohort_keys = {row.get("player_key") for row in cohort_players if isinstance(row, dict)}
    if len(cohort_keys) != len(cohort_players) or any(
        not isinstance(key, str) or not PLAYER_KEY.fullmatch(key) for key in cohort_keys
    ):
        raise ValueError("cohort player_key 오류")
    observation_match_ids = {row.get("match_id") for row in observations if isinstance(row, dict)}
    if len(observation_match_ids) > len(observations) or None in observation_match_ids:
        raise ValueError("observation match_id 오류")
    match_rows = [row for row in artifacts if row["dataset"] == "matches"]
    match_paths = {}
    match_hashes = {}
    for row in match_rows:
        match_id = Path(row["path"]).stem
        if match_id in match_paths:
            raise ValueError(f"match artifact 중복: {match_id}")
        match_paths[match_id] = sources["artifacts_by_path"][row["path"]]["resolved_path"]
        match_hashes[match_id] = row["sha256"]
    if not observation_match_ids <= set(match_paths):
        raise ValueError("observation match metadata 누락")

    raw_tokens = set()
    player_origins = {}
    player_categories = {}
    team_origins = {}
    match_members = {}
    key_namespace = Literal(
        f"{INSTANCE}keyspace/{quote(experiment, safe='')}/{quote(season, safe='')}",
        datatype=XSD.anyURI,
    )
    for match_id in sorted(observation_match_ids):
        document = _load_json(match_paths[match_id], dict, match_hashes[match_id])
        match_data = document.get("data")
        if not isinstance(match_data, dict) or match_data.get("id") != match_id:
            raise ValueError(f"match metadata ID 오류: {match_id}")
        attrs = match_data.get("attributes") or {}
        mode = attrs.get("gameMode")
        map_name = attrs.get("mapName")
        match_node = _iri("match", match_id)
        graph.add((match_node, RDF.type, PTW.Match))
        graph.add((match_node, PTW.matchId, _string(match_id, "match_id")))
        graph.add((match_node, PTW.mode, _string(mode, "match.mode")))
        graph.add((match_node, PTW.mapName, _string(map_name, "match.map")))
        included = document.get("included")
        if not isinstance(included, list):
            raise ValueError(f"match included 형식 오류: {match_id}")
        participant_rows = [
            row for row in included if isinstance(row, dict) and row.get("type") == "participant"
        ]
        participants = {}
        for row in participant_rows:
            participant_id = row.get("id")
            stats = (row.get("attributes") or {}).get("stats") or {}
            player_id = stats.get("playerId")
            if (
                not isinstance(participant_id, str)
                or not participant_id
                or not isinstance(player_id, str)
                or not player_id
                or participant_id in participants
            ):
                raise ValueError(f"participant identity 오류: {match_id}")
            player_key = digest(experiment, season, player_id)[:24]
            if player_origins.setdefault(player_key, player_id) != player_id:
                raise ValueError("player_key 충돌")
            category = (
                "account"
                if player_id.startswith("account.")
                else "ai"
                if player_id.startswith("ai.")
                else "other"
            )
            if player_categories.setdefault(player_key, category) != category:
                raise ValueError("player category 충돌")
            participants[participant_id] = player_key
            raw_tokens.add(player_id)
            if isinstance(stats.get("name"), str) and stats["name"]:
                raw_tokens.add(stats["name"])
            player_node = _iri("player", player_key)
            graph.add((player_node, RDF.type, PTW.ScopedPlayerIdentity))
            graph.add((player_node, PTW.playerKey, _string(player_key, "player_key")))
            graph.add((player_node, PTW.keyNamespace, key_namespace))
            graph.add((player_node, PTW.seasonId, _string(season, "season_id")))
            graph.add((player_node, PTW.identityCategory, _string(category, "identity_category")))
            graph.add((player_node, PTW.governedByExperiment, experiment_node))
        if len(participants) != len(set(participants.values())):
            raise ValueError(f"match player identity 중복: {match_id}")

        referenced_participants = []
        members = set()
        seen_teams = set()
        roster_rows = [
            row for row in included if isinstance(row, dict) and row.get("type") == "roster"
        ]
        for roster in roster_rows:
            team_id = ((roster.get("attributes") or {}).get("stats") or {}).get("teamId")
            if team_id is None:
                raise ValueError(f"roster teamId 누락: {match_id}")
            team_key = digest(experiment, match_id, team_id)[:24]
            origin = (match_id, str(team_id))
            if team_origins.setdefault(team_key, origin) != origin or team_key in seen_teams:
                raise ValueError("team_key 충돌 또는 중복")
            seen_teams.add(team_key)
            team_node = _iri("team", team_key)
            graph.add((team_node, RDF.type, PTW.TeamInstance))
            graph.add((team_node, PTW.teamKey, _string(team_key, "team_key")))
            graph.add((team_node, PTW.inMatch, match_node))
            refs = ((roster.get("relationships") or {}).get("participants") or {}).get("data")
            if not isinstance(refs, list) or not refs:
                raise ValueError(f"roster participant reference 오류: {match_id}")
            for ref in refs:
                participant_id = ref.get("id") if isinstance(ref, dict) else None
                if participant_id not in participants:
                    raise ValueError(f"roster participant 연결 실패: {match_id}")
                referenced_participants.append(participant_id)
                player_key = participants[participant_id]
                members.add(player_key)
                graph.add((_iri("player", player_key), PTW.memberOf, team_node))
        if Counter(referenced_participants) != Counter({key: 1 for key in participants}):
            raise ValueError(f"participant roster 귀속 불완전: {match_id}")
        match_members[match_id] = members

    observation_nodes = []
    seen_observations = set()
    for row in observations:
        if not isinstance(row, dict):
            raise ValueError("observation row 형식 오류")
        observation_id = row.get("observation_id")
        match_id = row.get("match_id")
        player_key = row.get("player_key")
        if (
            not isinstance(observation_id, str)
            or not PLAYER_KEY.fullmatch(observation_id)
            or observation_id in seen_observations
        ):
            raise ValueError("observation_id 오류")
        if (
            not isinstance(match_id, str)
            or not match_id
            or not isinstance(player_key, str)
            or not PLAYER_KEY.fullmatch(player_key)
            or player_key not in cohort_keys
            or player_key not in match_members.get(match_id, set())
        ):
            raise ValueError("observation player와 match 연결 오류")
        if row.get("season_id") != season:
            raise ValueError("observation season 연결 오류")
        status = row.get("status")
        if status not in STATUS_IRIS:
            raise ValueError(f"observation status 오류: {status}")
        seen_observations.add(observation_id)
        observation_node = _iri("observation", observation_id)
        observation_nodes.append(observation_node)
        graph.add((observation_node, RDF.type, PTW.Observation))
        graph.add((observation_node, PTW.observationId, _string(observation_id, "observation_id")))
        graph.add((observation_node, PTW.aboutPlayer, _iri("player", player_key)))
        graph.add((observation_node, PTW.measuredIn, _iri("match", match_id)))
        graph.add((observation_node, PTW.governedByExperiment, experiment_node))
        graph.add((observation_node, PTW.evaluatedByRule, rule_node))
        graph.add((observation_node, PTW.analysisStatus, STATUS_IRIS[status]))
        if row.get("skip_reason") is not None:
            skip = row["skip_reason"]
            if skip not in STATUS_IRIS:
                raise ValueError(f"observation skip_reason 오류: {skip}")
            graph.add((observation_node, PTW.skipReason, STATUS_IRIS[skip]))
        for predicate, key in (
            (PTW.seasonId, "season_id"),
            (PTW["split"], "split"),
            (PTW.mode, "mode"),
            (PTW.mapName, "map"),
        ):
            graph.add((observation_node, predicate, _string(row.get(key), f"observation.{key}")))
        for predicate, key, positive in (
            (PTW.rank, "rank", True),
            (PTW.rankDecile, "rank_decile", True),
            (PTW.recentIndex, "recent_index", True),
            (PTW.attacks, "attacks", False),
            (PTW.damageEvents, "damage_events", False),
            (PTW.minimumSignalPool, "minimum_signal_pool", True),
        ):
            graph.add(
                (
                    observation_node,
                    predicate,
                    _integer(row.get(key), f"observation.{key}", positive=positive),
                )
            )
        for predicate, key in (
            (PTW.ratio, "ratio"),
            (PTW.matchMean, "match_mean"),
            (PTW.matchSd, "match_sd"),
            (PTW.localZ, "local_z"),
        ):
            if row.get(key) is not None:
                graph.add((observation_node, predicate, _decimal(row[key], f"observation.{key}")))
        if row.get("eligible_players") is not None:
            graph.add(
                (
                    observation_node,
                    PTW.eligiblePlayers,
                    _integer(row["eligible_players"], "observation.eligible_players"),
                )
            )
        graph.add(
            (
                observation_node,
                PTW.reviewCandidate,
                _boolean(row.get("review_candidate"), "observation.review_candidate"),
            )
        )

    gold = sources["gold"]
    if gold.get("run_id") != run_id:
        raise ValueError("Gold run_id 연결 오류")
    denominators = gold.get("denominators") or {}
    primary = gold.get("primary") or {}
    secondary = gold.get("secondary") or {}
    result_node = _iri("result", run_id)
    graph.add((result_node, RDF.type, PTW.EvaluationResult))
    graph.add((result_node, PTW.runId, _string(run_id, "gold.run_id")))
    graph.add((result_node, PTW.governedByExperiment, experiment_node))
    graph.add((result_node, PTW.evaluatedByRule, rule_node))
    graph.add(
        (
            result_node,
            PTW.experimentStatus,
            _string(gold.get("experiment_status"), "gold.experiment_status"),
        )
    )
    for node in observation_nodes:
        graph.add((result_node, PTW.aggregatesObservation, node))
    for predicate, value, label in (
        (
            PTW.acceptedObservations,
            denominators.get("accepted_observations"),
            "accepted_observations",
        ),
        (
            PTW.primaryEvaluatedPlayers,
            primary.get("evaluated_players"),
            "primary.evaluated_players",
        ),
        (
            PTW.primaryReviewCandidates,
            primary.get("review_candidates"),
            "primary.review_candidates",
        ),
        (PTW.secondaryEvaluatedObservations, secondary.get("evaluated"), "secondary.evaluated"),
        (
            PTW.secondaryReviewCandidates,
            secondary.get("review_candidates"),
            "secondary.review_candidates",
        ),
    ):
        graph.add((result_node, predicate, _integer(value, f"gold.{label}")))
    graph.add((result_node, PROV.wasGeneratedBy, run_node))
    return (
        graph,
        raw_tokens,
        {
            "players": len(player_origins),
            "teams": len(team_origins),
            "matches": len(observation_match_ids),
            "observations": len(observation_nodes),
            "managed_artifacts": len(managed),
            "external_artifacts": len(artifact_nodes) - len(managed),
        },
    )


def _term_value(term):
    if term is None:
        return None
    if isinstance(term, URIRef):
        return str(term)
    if isinstance(term, BNode):
        return "anonymous"
    value = term.toPython() if isinstance(term, Literal) else str(term)
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral() else format(value, "f")
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)


def _query_rows(graph: Graph, query: str) -> list[dict]:
    result = graph.query(query)
    rows = [
        {str(variable): _term_value(row[index]) for index, variable in enumerate(result.vars)}
        for row in result
    ]
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=True))


def _violations(report: Graph) -> list[dict]:
    sh = Namespace("http://www.w3.org/ns/shacl#")
    rows = []
    for result in report.subjects(RDF.type, sh.ValidationResult):
        messages = sorted(str(value) for value in report.objects(result, sh.resultMessage))
        rows.append(
            {
                "focus_node": _term_value(report.value(result, sh.focusNode)),
                "result_path": _term_value(report.value(result, sh.resultPath)),
                "severity": _term_value(report.value(result, sh.resultSeverity)),
                "constraint": _term_value(report.value(result, sh.sourceConstraintComponent)),
                "messages": messages,
            }
        )
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=True))


def _canonical_ntriples(graph: Graph) -> bytes:
    rendered = graph.serialize(format="nt")
    lines = [line.rstrip("\r\n").encode("utf-8") for line in rendered.splitlines() if line.strip()]
    return b"\n".join(sorted(lines)) + b"\n"


def _gzip(body: bytes) -> bytes:
    target = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=target, compresslevel=9, mtime=0) as stream:
        stream.write(body)
    return target.getvalue()


def _hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


class RdfEngine:
    load_contract = staticmethod(_load_contract)

    def runtime(self):
        return {
            "python": ".".join(map(str, sys.version_info[:3])),
            "rdflib": version("rdflib"),
            "pyshacl": version("pyshacl"),
            "projector": PROJECTOR_VERSION,
        }

    def evaluate(
        self,
        run_id,
        sources,
        contract,
        experiment,
        rule,
        season,
        graph_summary,
        sql_summary,
        oracle_tokens,
    ):
        graph, raw_tokens, counts = _project_graph(sources, experiment, rule, season)
        conforms, report, _ = shacl_validate(
            graph,
            shacl_graph=contract["shapes"],
            ont_graph=contract["ontology"],
            inference="none",
            advanced=False,
            meta_shacl=True,
            do_owl_imports=False,
            abort_on_first=False,
            allow_infos=False,
            allow_warnings=False,
        )
        violation_rows = _violations(report)
        if not conforms:
            payload = {
                "schema_version": 1,
                "run_id": run_id,
                "ontology_version": ONTOLOGY_VERSION,
                "conforms": False,
                "violations": violation_rows,
            }
            raise SemanticConformanceError(f"SHACL 부적합: {len(violation_rows)}건", payload)

        body = _canonical_ntriples(graph)
        repeated_body = _canonical_ntriples(graph)
        compressed = _gzip(body)
        repeated_compressed = _gzip(repeated_body)
        graph_terms = {str(term) for triple in graph for term in triple}
        token_matches = sorted((raw_tokens | oracle_tokens) & graph_terms)
        static_secret_markers = sum(
            marker in body for marker in (b"PUBG_API_KEY", b"Authorization: Bearer")
        )
        blank_nodes = sum(isinstance(term, BNode) for triple in graph for term in triple)

        expected = _expected_queries(graph_summary, sql_summary)
        competency = {}
        for query_id, query in contract["queries"].items():
            actual = _query_rows(graph, query["text"])
            competency[query_id] = {
                "status": "PASS" if actual == expected[query_id] else "FAIL",
                "actual": actual,
                "expected": expected[query_id],
            }
        checks = [
            _check(
                "semantic.shacl", bool(conforms), bool(conforms), True, "SHACL Core와 Meta-SHACL"
            ),
            _check(
                "semantic.blank_nodes",
                blank_nodes == 0,
                blank_nodes,
                0,
                "instance graph blank node",
            ),
            _check(
                "semantic.raw_identity",
                not token_matches,
                len(token_matches),
                0,
                "원 identity exact token",
            ),
            _check(
                "semantic.secret_marker",
                static_secret_markers == 0,
                static_secret_markers,
                0,
                "secret marker",
            ),
            _check(
                "semantic.replay",
                body == repeated_body and compressed == repeated_compressed,
                {"nt": _hash(repeated_body), "gzip": _hash(repeated_compressed)},
                {"nt": _hash(body), "gzip": _hash(compressed)},
                "동일 graph 재직렬화",
            ),
            *[
                _check(
                    f"semantic.{query_id.lower()}",
                    row["status"] == "PASS",
                    row["actual"],
                    row["expected"],
                    "frozen competency query parity",
                )
                for query_id, row in competency.items()
            ],
        ]
        failed = [row["id"] for row in checks if row["status"] != "PASS"]
        validation = {
            "schema_version": 1,
            "run_id": run_id,
            "ontology_version": ONTOLOGY_VERSION,
            "projector_version": PROJECTOR_VERSION,
            "conforms": not failed,
            "violations": violation_rows,
            "graph": {
                **counts,
                "triples": len(graph),
                "ntriples_sha256": _hash(body),
                "gzip_sha256": _hash(compressed),
            },
            "privacy": {
                "raw_token_matches": len(token_matches),
                "secret_marker_matches": static_secret_markers,
                "blank_nodes": blank_nodes,
            },
            "competency_queries": competency,
            "checks": checks,
        }
        if failed:
            raise SemanticConformanceError(f"semantic parity 실패: {', '.join(failed)}", validation)

        return {
            "body": body,
            "compressed": compressed,
            "validation": validation,
            "checks": checks,
            "triples": len(graph),
        }
