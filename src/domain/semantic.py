"""Semantic protocol and expected query contracts, independent of RDF libraries."""

import json
from .research import LEGACY_PROTOCOL_VERSION, PROTOCOL_VERSION
from .pubg.parsing import LEGACY_RULE_PROTOCOL_VERSION, RULE_PROTOCOL_VERSION

ONTOLOGY_IRI = "https://procloudkim.github.io/pubg-telemetry-watch/ontology/pubg-watch.ttl"
STATUS_IRIS = {
    "evaluated": ONTOLOGY_IRI + "#statusEvaluated",
    "target_below_min_attacks": ONTOLOGY_IRI + "#statusTargetBelowMinAttacks",
    "match_pool_below_8": ONTOLOGY_IRI + "#statusMatchPoolBelow8",
    "match_pool_below_signal_capable": ONTOLOGY_IRI + "#statusMatchPoolBelowSignalCapable",
}


def _resolve_protocols(sources: dict) -> tuple[str, str, str]:
    manifest = sources["manifest"]
    cohort = sources["cohort"]
    protocol = sources["protocol"]
    gold = sources["gold"]
    experiment = manifest.get("protocol_version")
    if experiment not in {LEGACY_PROTOCOL_VERSION, PROTOCOL_VERSION}:
        raise ValueError(f"지원하지 않는 v3 protocol: {experiment}")
    if any(
        value != experiment
        for value in (
            cohort.get("protocol_version"),
            protocol.get("protocol_version"),
            gold.get("protocol_version"),
        )
    ):
        raise ValueError("experiment protocol 연결 불일치")
    expected_rule = (
        LEGACY_RULE_PROTOCOL_VERSION
        if experiment == LEGACY_PROTOCOL_VERSION
        else RULE_PROTOCOL_VERSION
    )
    explicit_rules = [
        protocol.get("rule_protocol_version"),
        gold.get("rule_protocol_version"),
        *(row.get("rule_protocol_version") for row in sources["observations"]),
    ]
    if any(value != expected_rule for value in explicit_rules if value is not None):
        raise ValueError("rule protocol 연결 불일치")
    season = cohort.get("season_id")
    if not isinstance(season, str) or not season:
        raise ValueError("cohort season_id 오류")
    return experiment, expected_rule, season


def _expected_queries(graph_summary: dict, sql_summary: dict) -> dict:
    observations = graph_summary["source"]["observations"]
    funnel = sql_summary["funnel"]
    return {
        "CQ1": [
            {
                "observations": observations,
                "playerLinks": observations,
                "matchLinks": observations,
                "experimentLinks": observations,
                "ruleLinks": observations,
            }
        ],
        "CQ2": [{"repeatedPairs": graph_summary["relationship_query"]["repeated_at_least_2"]}],
        "CQ3": [{"lineageEdges": graph_summary["lineage_query"]["edges"], "cycleNodes": 0}],
        "CQ4": sorted(
            [
                {"status": str(STATUS_IRIS[status]), "count": funnel[status]}
                for status in STATUS_IRIS
                if funnel[status]
            ],
            key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=True),
        ),
        "CQ5": [
            {
                "primaryPlayers": sql_summary["primary"]["evaluated_players"],
                "primaryCandidates": sql_summary["primary"]["review_candidates"],
            }
        ],
        "CQ6": [{"results": 1, "resultObservations": funnel["accepted_observations"]}],
    }


ONTOLOGY_VERSION = "1.0.0"

PROJECTOR_VERSION = "semantic-shadow-1"

QUERY_FILES = {
    "CQ1": "cq1-observation-path.rq",
    "CQ2": "cq2-repeated-teammates.rq",
    "CQ3": "cq3-lineage.rq",
    "CQ4": "cq4-status-partition.rq",
    "CQ5": "cq5-primary-result.rq",
    "CQ6": "cq6-result-lineage.rq",
}
