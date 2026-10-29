"""In-memory graph and lineage consistency calculations."""

import hashlib
import json
from collections import Counter, defaultdict, deque
from itertools import combinations
from pathlib import PurePosixPath
import re
from .serialization import digest

PLAYER_KEY = re.compile(r"[0-9a-f]{24}")


def _check(check_id, ok, observed, expected, detail):
    return {
        "id": check_id,
        "status": "PASS" if ok else "FAIL",
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }


def _projection_hash(nodes, edges):
    body = json.dumps(
        {"nodes": sorted(nodes), "edges": sorted(edges)}, ensure_ascii=True, separators=(",", ":")
    )
    return hashlib.sha256(body.encode()).hexdigest()


def _lineage(manifest, nodes, edges):
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("manifest artifact 형식 오류")
    paths = [row.get("path") for row in artifacts]
    if any(not isinstance(path, str) or not path for path in paths) or len(paths) != len(
        set(paths)
    ):
        raise ValueError("manifest artifact path 오류")

    artifact_paths = set(paths)
    adjacency = defaultdict(list)
    lineage_edges = []
    for row in artifacts:
        derived_from = row.get("derived_from")
        if not isinstance(derived_from, list) or any(
            not isinstance(path, str) for path in derived_from
        ):
            raise ValueError("manifest derived_from 형식 오류")
        nodes.add(("artifact", row["path"]))
        for source in derived_from:
            nodes.add(("artifact", source))
            edge = (("artifact", row["path"]), "derived_from", ("artifact", source))
            edges.add(edge)
            lineage_edges.append((row["path"], source))
            adjacency[row["path"]].append(source)
    if len(lineage_edges) != len(set(lineage_edges)):
        raise ValueError("manifest lineage edge 중복")

    lineage_nodes = artifact_paths | {source for _, source in lineage_edges}
    indegree = {path: 0 for path in lineage_nodes}
    for _, source in lineage_edges:
        indegree[source] += 1
    queue = deque(path for path, count in indegree.items() if count == 0)
    visited = 0
    while queue:
        path = queue.popleft()
        visited += 1
        for source in adjacency[path]:
            indegree[source] -= 1
            if indegree[source] == 0:
                queue.append(source)
    cyclic = visited != len(lineage_nodes)

    gold = {row["path"] for row in artifacts if row.get("layer") == "gold"}
    reachable = set(gold)
    queue = deque(gold)
    while queue:
        path = queue.popleft()
        for source in adjacency[path]:
            if source not in reachable:
                reachable.add(source)
                queue.append(source)
    depth_cache = {}

    def depth(path):
        if path not in depth_cache:
            depth_cache[path] = max((depth(source) + 1 for source in adjacency[path]), default=0)
        return depth_cache[path]

    max_depth = max((depth(path) for path in gold), default=0) if not cyclic else 0
    return {
        "artifact_nodes": len(lineage_nodes),
        "managed_artifacts": len(artifact_paths),
        "external_source_nodes": len(lineage_nodes - artifact_paths),
        "edges": len(lineage_edges),
        "cyclic": cyclic,
        "gold_starts": len(gold),
        "gold_reachable_sources": len(reachable - gold),
        "maximum_depth": max_depth,
    }


def project_run(
    run_id,
    cohort,
    observations,
    manifest,
    match_documents,
    parsed_by_match,
    source_hashes,
    available_match_files,
):
    protocol = cohort.get("protocol_version")
    season = cohort.get("season_id")
    cohort_rows = cohort.get("players")
    if (
        not isinstance(protocol, str)
        or not isinstance(season, str)
        or not isinstance(cohort_rows, list)
    ):
        raise ValueError("cohort 핵심 필드 오류")

    cohort_keys = [row.get("player_key") for row in cohort_rows if isinstance(row, dict)]
    if (
        len(cohort_keys) != len(cohort_rows)
        or any(not isinstance(key, str) or not PLAYER_KEY.fullmatch(key) for key in cohort_keys)
        or len(cohort_keys) != len(set(cohort_keys))
    ):
        raise ValueError("cohort player_key 오류")
    observation_ids = [row.get("observation_id") for row in observations if isinstance(row, dict)]
    match_ids = [row.get("match_id") for row in observations if isinstance(row, dict)]
    observation_keys = [row.get("player_key") for row in observations if isinstance(row, dict)]
    if (
        len(observation_ids) != len(observations)
        or any(not isinstance(value, str) or not value for value in observation_ids + match_ids)
        or any(
            not isinstance(key, str) or not PLAYER_KEY.fullmatch(key) for key in observation_keys
        )
        or len(observation_ids) != len(set(observation_ids))
    ):
        raise ValueError("observation key 오류")
    if any(PurePosixPath(match_id).name != match_id for match_id in match_ids):
        raise ValueError("observation match_id 경로 오류")

    match_ids = set(match_ids)
    nodes = set()
    edges = set()
    raw_tokens = set()
    player_origins = {}
    player_categories = {}
    team_origins = {}
    match_players = defaultdict(set)
    teammate_counts = Counter()
    players_with_teammates = set()
    participant_rows = 0
    membership_edges = 0
    unresolved_references = 0
    non_squad_matches = 0

    match_digest = hashlib.sha256()
    for filename, source_sha256, document in match_documents:
        match_digest.update(filename.encode())
        match_digest.update(bytes.fromhex(source_sha256))
        match = document.get("data")
        if not isinstance(match, dict) or match.get("id") != filename.removesuffix(".json"):
            raise ValueError("match metadata ID 불일치")
        match_id = match["id"]
        if (match.get("attributes") or {}).get("gameMode") != "squad-fpp":
            non_squad_matches += 1
        nodes.add(("match", match_id))

        included = document.get("included")
        if not isinstance(included, list):
            raise ValueError("match included 형식 오류")
        participant_items = [
            row for row in included if isinstance(row, dict) and row.get("type") == "participant"
        ]
        participant_ids = [row.get("id") for row in participant_items]
        if any(not isinstance(value, str) or not value for value in participant_ids) or len(
            participant_ids
        ) != len(set(participant_ids)):
            raise ValueError("participant ID 오류")

        participants = {}
        for row in participant_items:
            stats = (row.get("attributes") or {}).get("stats") or {}
            player_id = stats.get("playerId")
            if not isinstance(player_id, str) or not player_id:
                raise ValueError("participant playerId 누락")
            player_key = digest(protocol, season, player_id)[:24]
            previous = player_origins.setdefault(player_key, player_id)
            if previous != player_id:
                raise ValueError("player_key 충돌")
            category = (
                "account"
                if player_id.startswith("account.")
                else "ai"
                if player_id.startswith("ai.")
                else "other"
            )
            if player_categories.setdefault(player_key, category) != category:
                raise ValueError("player key category 불일치")
            participants[row["id"]] = player_key
            nodes.add(("player", player_key))
            raw_tokens.add(player_id)
            if isinstance(stats.get("name"), str) and stats["name"]:
                raw_tokens.add(stats["name"])
        if len(participants) != len(set(participants.values())):
            raise ValueError("match playerId 중복")
        participant_rows += len(participants)

        roster_items = [
            row for row in included if isinstance(row, dict) and row.get("type") == "roster"
        ]
        referenced_participants = []
        seen_teams = set()
        for roster in roster_items:
            team_id = ((roster.get("attributes") or {}).get("stats") or {}).get("teamId")
            if team_id is None:
                raise ValueError("roster teamId 누락")
            team_key = digest(protocol, match_id, team_id)[:24]
            origin = (match_id, str(team_id))
            previous = team_origins.setdefault(team_key, origin)
            if previous != origin or team_key in seen_teams:
                raise ValueError("team_key 충돌 또는 중복")
            seen_teams.add(team_key)
            team_node = ("team", team_key)
            nodes.add(team_node)
            edges.add((team_node, "in_match", ("match", match_id)))

            refs = ((roster.get("relationships") or {}).get("participants") or {}).get("data")
            if not isinstance(refs, list) or not refs:
                raise ValueError("roster participant reference 오류")
            members = []
            for ref in refs:
                participant_id = ref.get("id") if isinstance(ref, dict) else None
                if participant_id not in participants:
                    unresolved_references += 1
                    continue
                referenced_participants.append(participant_id)
                members.append(participants[participant_id])
            if len(members) != len(set(members)):
                raise ValueError("roster player 중복")
            members.sort()
            match_players[match_id].update(members)
            if len(members) > 1:
                players_with_teammates.update(members)
            for player_key in members:
                edges.add((("player", player_key), "member_of", team_node))
                membership_edges += 1
            teammate_counts.update(combinations(members, 2))
        if Counter(referenced_participants) != Counter({key: 1 for key in participants}):
            raise ValueError("participant roster 귀속 불완전")

    observed_in_match = 0
    parsed_direct = 0
    for row in observations:
        observation_node = ("observation", row["observation_id"])
        player_node = ("player", row["player_key"])
        match_node = ("match", row["match_id"])
        nodes.add(observation_node)
        edges.add((player_node, "observed_as", observation_node))
        edges.add((observation_node, "measured_in", match_node))
        observed_in_match += row["player_key"] in match_players[row["match_id"]]
        parsed = parsed_by_match[row["match_id"]]
        players = parsed.get("players")
        if not isinstance(players, dict):
            raise ValueError("parsed players 형식 오류")
        parsed_direct += row["player_key"] in players

    lineage = _lineage(manifest, nodes, edges)
    orphan_edges = sum(source not in nodes or target not in nodes for source, _, target in edges)
    node_counts = Counter(label for label, _ in nodes)
    edge_counts = Counter(edge_type for _, edge_type, _ in edges)
    projection_sha256 = _projection_hash(nodes, edges)
    replay_sha256 = _projection_hash(reversed(sorted(nodes)), reversed(sorted(edges)))
    observed_key_set = set(observation_keys)
    repeated_pairs = sum(count >= 2 for count in teammate_counts.values())
    repeated_by_category = Counter(
        "+".join(sorted((player_categories[pair[0]], player_categories[pair[1]])))
        for pair, count in teammate_counts.items()
        if count >= 2
    )

    checks = [
        _check(
            "source.manifest_quality",
            (manifest.get("quality") or {}).get("status") == "PASS",
            (manifest.get("quality") or {}).get("status"),
            "PASS",
            "입력 v3 manifest 품질",
        ),
        _check(
            "source.manifest_protocol",
            manifest.get("protocol_version") == protocol,
            manifest.get("protocol_version"),
            protocol,
            "manifest와 cohort protocol 일치",
        ),
        _check(
            "source.manifest_run",
            manifest.get("run_id") == run_id,
            manifest.get("run_id"),
            run_id,
            "manifest와 요청 run 일치",
        ),
        _check(
            "source.match_metadata",
            len(match_documents) == len(match_ids),
            len(match_documents),
            len(match_ids),
            "Silver observation match metadata coverage",
        ),
        _check(
            "source.mode", non_squad_matches == 0, non_squad_matches, 0, "squad-fpp 외 match 수"
        ),
        _check(
            "graph.participant_reference",
            unresolved_references == 0,
            unresolved_references,
            0,
            "해결되지 않은 roster participant reference",
        ),
        _check(
            "graph.membership",
            membership_edges == participant_rows,
            membership_edges,
            participant_rows,
            "participant당 team membership 1개",
        ),
        _check("graph.orphan", orphan_edges == 0, orphan_edges, 0, "endpoint 없는 edge"),
        _check(
            "graph.observation_path",
            observed_in_match == len(observations),
            observed_in_match,
            len(observations),
            "observation player가 해당 match roster에 존재",
        ),
        _check(
            "graph.observation_cohort",
            set(observation_keys) <= set(cohort_keys),
            len(set(observation_keys) & set(cohort_keys)),
            len(set(observation_keys)),
            "observation player_key의 cohort 참조",
        ),
        _check(
            "graph.repeated_pair",
            repeated_pairs > 0,
            repeated_pairs,
            ">=1",
            "2판 이상 반복 teammate pair",
        ),
        _check(
            "graph.projection_replay",
            projection_sha256 == replay_sha256,
            replay_sha256,
            projection_sha256,
            "입력 순서 독립 projection hash",
        ),
        _check(
            "lineage.acyclic",
            not lineage["cyclic"],
            int(lineage["cyclic"]),
            0,
            "manifest lineage cycle",
        ),
        _check(
            "lineage.gold_root",
            lineage["gold_starts"] > 0,
            lineage["gold_starts"],
            ">=1",
            "lineage 출발 Gold artifact",
        ),
    ]
    return {
        "run_id": run_id,
        "protocol_version": protocol,
        "source": {
            "available_match_metadata": available_match_files,
            "selected_matches": len(match_ids),
            "observations": len(observations),
            "source_sha256": {
                "cohort": source_hashes["cohort"],
                "observations": source_hashes["observations"],
                "manifest": source_hashes["manifest"],
                "selected_matches": match_digest.hexdigest(),
            },
        },
        "graph": {
            "nodes": dict(sorted(node_counts.items())),
            "total_nodes": len(nodes),
            "edges": dict(sorted(edge_counts.items())),
            "total_edges": len(edges),
            "projection_sha256": projection_sha256,
        },
        "relationship_query": {
            "players": node_counts["player"],
            "teams": node_counts["team"],
            "memberships": edge_counts["member_of"],
            "players_by_key_type": dict(sorted(Counter(player_categories.values()).items())),
            "unique_teammate_pairs": len(teammate_counts),
            "repeated_at_least_2": repeated_pairs,
            "repeated_at_least_3": sum(count >= 3 for count in teammate_counts.values()),
            "repeated_by_key_type": dict(sorted(repeated_by_category.items())),
            "maximum_repeat": max(teammate_counts.values(), default=0),
            "repeated_touching_observed": sum(
                count >= 2 and bool(set(pair) & observed_key_set)
                for pair, count in teammate_counts.items()
            ),
            "observed_players_with_teammate": len(observed_key_set & players_with_teammates),
        },
        "key_query": {
            "cohort_players": len(cohort_keys),
            "cohort_in_selected_graph": len(set(cohort_keys) & set(player_origins)),
            "observed_unique_players": len(observed_key_set),
            "observed_in_selected_graph": len(observed_key_set & set(player_origins)),
            "observation_rows_in_own_match": observed_in_match,
            "parsed_direct_rows": parsed_direct,
        },
        "lineage_query": lineage,
        "checks": checks,
    }, raw_tokens


def required_match_ids(observations):
    ids = [row.get("match_id") for row in observations if isinstance(row, dict)]
    if len(ids) != len(observations) or any(
        not isinstance(value, str) or not value or PurePosixPath(value).name != value
        for value in ids
    ):
        raise ValueError("observation match_id 경로 오류")
    return sorted(set(ids))
