"""Frozen cohort, denominator and statistical decisions; no I/O."""

import json
import math
import random
from collections import Counter, defaultdict
from .serialization import digest
from .quality import _check, _quality

LEGACY_PROTOCOL_VERSION = "v3-r2-top100-2"

PROTOCOL_VERSION = "v3-r2-top100-3"

PREFLIGHT_VERSION = "v3-cohort-coverage-1"

COHORT_SIZE = 100

MATCHES_PER_PLAYER = 5

API_INTERVAL_S = 7

MIN_PRIMARY_PLAYERS = 59

MIN_SECONDARY_OBSERVATIONS = 150

REVIEW_RATE_GUARDRAIL = 0.05

BOOTSTRAP_REPLICATES = 2_000


def split_players(leaders, season_id):
    if len(leaders) != COHORT_SIZE:
        raise ValueError(f"top100 인원 불일치: {len(leaders)}")
    ranks = [(row.get("attributes") or {}).get("rank") for row in leaders]
    ids = [row.get("id") for row in leaders]
    if (
        any(not isinstance(rank, int) for rank in ranks)
        or sorted(ranks) != list(range(1, COHORT_SIZE + 1))
        or len(set(ids)) != COHORT_SIZE
    ):
        raise ValueError("rank 1~100 또는 player ID 유일성 실패")
    by_decile = defaultdict(list)
    for row in leaders:
        rank = (row.get("attributes") or {}).get("rank")
        if not isinstance(rank, int) or not 1 <= rank <= COHORT_SIZE:
            raise ValueError(f"rank 범위 오류: {rank}")
        by_decile[(rank - 1) // 10 + 1].append(row)
    if set(by_decile) != set(range(1, 11)) or any(len(rows) != 10 for rows in by_decile.values()):
        raise ValueError("rank 10개 구간이 각 10명이 아님")
    return {row["id"]: ("holdout", decile) for decile, rows in by_decile.items() for row in rows}


def make_cohort(
    leaders,
    player_payloads,
    season_id,
    started_at,
    completed_at,
    source_hashes,
    excluded_match_ids=(),
    protocol_version=PROTOCOL_VERSION,
):
    split_by_id = split_players(leaders, season_id)
    excluded_match_ids = set(excluded_match_ids)
    players_by_id = {
        row["id"]: row for payload in player_payloads for row in payload.get("data", [])
    }
    result = []
    for leader in sorted(leaders, key=lambda row: row["attributes"]["rank"]):
        player_id = leader["id"]
        if player_id not in players_by_id:
            raise ValueError("player batch에서 leaderboard ID 누락")
        split, decile = split_by_id[player_id]
        recent_rows = (
            players_by_id[player_id]
            .get("relationships", {})
            .get("matches", {})
            .get("data", [])[:MATCHES_PER_PLAYER]
        )
        match_ids = [row["id"] for row in recent_rows if row["id"] not in excluded_match_ids]
        result.append(
            {
                "player_key": digest(protocol_version, season_id, player_id)[:24],
                "rank": leader["attributes"]["rank"],
                "rank_decile": decile,
                "split": split,
                "prior_excluded_references": sum(
                    row["id"] in excluded_match_ids for row in recent_rows
                ),
                "recent_match_ids": match_ids,
            }
        )
    return {
        "protocol_version": protocol_version,
        "season_id": season_id,
        "snapshot_started_at": started_at,
        "snapshot_completed_at": completed_at,
        "source_sha256": source_hashes,
        "excluded_prior_match_ids": sorted(excluded_match_ids),
        "prior_excluded_references": sum(row["prior_excluded_references"] for row in result),
        "players": result,
    }


def candidate_matches(cohort):
    protocol_version = cohort.get("protocol_version", PROTOCOL_VERSION)
    contenders = defaultdict(dict)
    for player in cohort["players"]:
        for recent_index, match_id in enumerate(player["recent_match_ids"], 1):
            previous = contenders[match_id].get(player["player_key"])
            if previous is None or recent_index < previous["recent_index"]:
                contenders[match_id][player["player_key"]] = {
                    "match_id": match_id,
                    "player_key": player["player_key"],
                    "rank": player["rank"],
                    "rank_decile": player["rank_decile"],
                    "split": player["split"],
                    "recent_index": recent_index,
                }
    selected = []
    for match_id, by_player in contenders.items():
        owner = min(
            by_player.values(),
            key=lambda row: digest(protocol_version, match_id, row["player_key"]),
        )
        selected.append(owner)
    return sorted(
        selected,
        key=lambda row: (
            row["recent_index"],
            (row["rank"] - 1) % 10,
            row["rank_decile"],
            row["match_id"],
        ),
    )


def cohort_preflight(cohort):
    players = cohort["players"]
    candidates = candidate_matches(cohort)
    source_players = {row["player_key"] for row in players if row["recent_match_ids"]}
    owner_players = {row["player_key"] for row in candidates}
    by_decile = {}
    for decile in range(1, 11):
        members = [row for row in players if row["rank_decile"] == decile]
        member_keys = {row["player_key"] for row in members}
        owned = [row for row in candidates if row["rank_decile"] == decile]
        by_decile[str(decile)] = {
            "cohort_players": len(members),
            "source_reference_players": sum(bool(row["recent_match_ids"]) for row in members),
            "candidate_owner_players": len(member_keys & owner_players),
            "candidate_matches": len(owned),
            "prior_excluded_references": sum(
                row.get("prior_excluded_references", 0) for row in members
            ),
        }
    checks = [
        _check(
            "v3.preflight.source_player_coverage",
            "completeness",
            len(source_players) == COHORT_SIZE,
            len(source_players),
            COHORT_SIZE,
            "prior 제외 뒤 match reference가 있는 cohort 플레이어",
        ),
        _check(
            "v3.preflight.owner_player_coverage",
            "completeness",
            len(owner_players) == COHORT_SIZE,
            len(owner_players),
            COHORT_SIZE,
            "공유 match 단일 귀속 뒤 후보를 소유한 cohort 플레이어",
        ),
        _check(
            "v3.preflight.primary_ceiling",
            "validity",
            len(owner_players) >= MIN_PRIMARY_PLAYERS,
            len(owner_players),
            f">={MIN_PRIMARY_PLAYERS}",
            "mode/R2 필터 전 가능한 1차 최대 분모",
        ),
        _check(
            "v3.preflight.secondary_ceiling",
            "validity",
            len(candidates) >= MIN_SECONDARY_OBSERVATIONS,
            len(candidates),
            f">={MIN_SECONDARY_OBSERVATIONS}",
            "mode/R2 필터 전 가능한 2차 최대 분모",
        ),
    ]
    return {
        "preflight_version": PREFLIGHT_VERSION,
        "protocol_version": cohort["protocol_version"],
        "cohort_players": len(players),
        "source_reference_players": len(source_players),
        "candidate_owner_players": len(owner_players),
        "candidate_matches": len(candidates),
        "prior_excluded_references": cohort.get("prior_excluded_references", 0),
        "primary_minimum": MIN_PRIMARY_PLAYERS,
        "secondary_minimum": MIN_SECONDARY_OBSERVATIONS,
        "by_rank_decile": by_decile,
        "boundary": "mode 및 R2 적격성 적용 전 이론상 최대치",
        **_quality(checks),
    }


def binomial_cdf(k, n, probability):
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(
        math.comb(n, value) * probability**value * (1 - probability) ** (n - value)
        for value in range(k + 1)
    )


def _cdf_root(k, n, target):
    low, high = 0.0, 1.0
    for _ in range(80):
        middle = (low + high) / 2
        if binomial_cdf(k, n, middle) > target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def clopper_pearson_one_sided(successes, total, confidence=0.95):
    if total < 1 or not 0 <= successes <= total:
        raise ValueError("0 <= successes <= total, total >= 1 필요")
    alpha = 1 - confidence
    lower = 0.0 if successes == 0 else _cdf_root(successes - 1, total, 1 - alpha)
    upper = 1.0 if successes == total else _cdf_root(successes, total, alpha)
    return lower, upper


def wilson_interval(successes, total, z=1.959963984540054):
    if total < 1 or not 0 <= successes <= total:
        raise ValueError("0 <= successes <= total, total >= 1 필요")
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    radius = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    lower = 0.0 if successes == 0 else max(0.0, center - radius)
    upper = 1.0 if successes == total else min(1.0, center + radius)
    return lower, upper


def cluster_bootstrap_interval(observations, seed, replicates=BOOTSTRAP_REPLICATES):
    groups = defaultdict(list)
    for row in observations:
        groups[row["player_key"]].append(row)
    keys = sorted(groups)
    if not keys:
        return None
    rng = random.Random(seed)
    rates = []
    for _ in range(replicates):
        sampled = [rng.choice(keys) for _ in keys]
        rows = [row for key in sampled for row in groups[key]]
        rates.append(sum(row["review_candidate"] for row in rows) / len(rows))
    rates.sort()
    return rates[int(0.025 * (replicates - 1))], rates[int(0.975 * (replicates - 1))]


def primary_decision(successes, total):
    if total < MIN_PRIMARY_PLAYERS:
        return {"status": "INSUFFICIENT_SAMPLE", "lower": None, "upper": None}
    lower, upper = clopper_pearson_one_sided(successes, total)
    if upper < REVIEW_RATE_GUARDRAIL:
        status = "CRITERION_SUPPORTED"
    elif lower >= REVIEW_RATE_GUARDRAIL:
        status = "CRITERION_NOT_SUPPORTED"
    else:
        status = "INCONCLUSIVE"
    return {"status": status, "lower": lower, "upper": upper}


def _rate_summary(rows):
    total = len(rows)
    signals = sum(row["review_candidate"] for row in rows)
    interval = wilson_interval(signals, total) if total else (None, None)
    return {
        "review_candidates": signals,
        "evaluated": total,
        "review_candidate_rate": signals / total if total else None,
        "wilson_95": list(interval),
    }


def _subgroups(rows, field):
    groups = defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    return {key: _rate_summary(values) for key, values in sorted(groups.items())}


def _status_groups(rows, field):
    groups = defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    return {
        key: {"accepted": len(values), **dict(Counter(row["status"] for row in values))}
        for key, values in sorted(groups.items())
    }


def _v3_checks(
    cohort,
    candidates,
    observations,
    collection,
    data_errors,
    raw_identities,
    pseudonymous_errors,
    source_hashes_match,
    cohort_reproducible,
    api_stats,
    preflight,
    rule_protocol,
):
    players = cohort["players"]
    splits = Counter(row["split"] for row in players)
    states = Counter(row["status"] for row in observations)
    prior_overlap = len(
        {row["match_id"] for row in candidates} & set(cohort.get("excluded_prior_match_ids", ()))
    )
    observed_text = json.dumps(observations, ensure_ascii=False)
    leaked = sum(
        bool(identity["account_id"] and identity["account_id"] in observed_text)
        or bool(identity["name"] and identity["name"] in observed_text)
        for identity in raw_identities.values()
    )
    return [
        _check(
            "v3.cohort_size", "completeness", len(players) == 100, len(players), 100, "동결 cohort"
        ),
        _check(
            "v3.rank_unique",
            "uniqueness",
            {row["rank"] for row in players} == set(range(1, 101)),
            len({row["rank"] for row in players}),
            100,
            "rank 1~100",
        ),
        _check(
            "v3.player_key_unique",
            "uniqueness",
            len({row["player_key"] for row in players}) == 100,
            len({row["player_key"] for row in players}),
            100,
            "비식별 player_key",
        ),
        _check(
            "v3.split",
            "consistency",
            splits == {"holdout": 100},
            dict(splits),
            {"holdout": 100},
            "top100 내부 holdout",
        ),
        _check(
            "v3.snapshot_hashes",
            "integrity",
            source_hashes_match,
            source_hashes_match,
            True,
            "동결 source SHA-256 재검산",
        ),
        _check(
            "v3.cohort_reproducible",
            "consistency",
            cohort_reproducible,
            cohort_reproducible,
            True,
            "원 API payload에서 cohort·split 재생성",
        ),
        _check(
            "v3.snapshot_time",
            "timeliness",
            bool(
                cohort.get("snapshot_started_at")
                and cohort.get("snapshot_completed_at")
                and cohort["snapshot_started_at"] <= cohort["snapshot_completed_at"]
            ),
            {
                "started": cohort.get("snapshot_started_at"),
                "completed": cohort.get("snapshot_completed_at"),
            },
            "started <= completed",
            "snapshot 구간",
        ),
        _check(
            "v3.api_call_limit",
            "validity",
            api_stats["max_calls_per_session"] <= 60,
            api_stats["max_calls_per_session"],
            "<=60",
            "세션별 인증 API 호출 수",
        ),
        _check(
            "v3.api_interval",
            "timeliness",
            api_stats["minimum_interval_s"] is None
            or api_stats["minimum_interval_s"] >= API_INTERVAL_S,
            api_stats["minimum_interval_s"],
            f">={API_INTERVAL_S}",
            "원장 requested_at 기준 요청 간격",
            severity="WARN",
        ),
        _check(
            "v3.candidate_unique",
            "uniqueness",
            len({row["match_id"] for row in candidates}) == len(candidates),
            len(candidates) - len({row["match_id"] for row in candidates}),
            0,
            "공유 match 단일 귀속",
        ),
        _check(
            "v3.cohort_coverage_preflight",
            "completeness",
            preflight["status"] == "PASS",
            {
                "source_reference_players": preflight["source_reference_players"],
                "candidate_owner_players": preflight["candidate_owner_players"],
            },
            {"source_reference_players": COHORT_SIZE, "candidate_owner_players": COHORT_SIZE},
            "후속 실행에서는 collect 전 차단; 기존 완료 run은 해석 WARN",
            severity="WARN",
        ),
        _check(
            "v3.prior_exposure",
            "referential_integrity",
            prior_overlap == 0,
            prior_overlap,
            0,
            "v1/v2 및 이전 v3 동결 후보와 현재 후보의 중복 수",
        ),
        _check(
            "v3.collection",
            "completeness",
            collection.get("pending", 0) == 0
            and collection.get("api_error", 0) == 0
            and collection.get("telemetry_pending", 0) == 0,
            {key: collection.get(key, 0) for key in ("pending", "api_error", "telemetry_pending")},
            {"pending": 0, "api_error": 0, "telemetry_pending": 0},
            "frozen reference 수집 완료",
        ),
        _check(
            "v3.collection_denominator",
            "consistency",
            collection.get("frozen_unique_references") == len(candidates),
            collection.get("frozen_unique_references"),
            len(candidates),
            "수집 상태 합계와 고정 후보",
        ),
        _check(
            "v3.data_errors",
            "validity",
            not data_errors,
            len(data_errors),
            0,
            "target 식별·스키마 오류",
        ),
        _check(
            "v3.observation_denominator",
            "consistency",
            len(observations) == collection.get("ready", 0),
            len(observations),
            collection.get("ready", 0),
            "채택 mode ready와 Silver 관측 수",
        ),
        _check(
            "v3.observation_unique",
            "uniqueness",
            len({row["observation_id"] for row in observations}) == len(observations),
            len(observations) - len({row["observation_id"] for row in observations}),
            0,
            "observation ID",
        ),
        _check(
            "v3.mode",
            "validity",
            all(row["mode"] == "squad-fpp" for row in observations),
            sum(row["mode"] != "squad-fpp" for row in observations),
            0,
            "Silver 관측 mode",
        ),
        _check(
            "v3.status",
            "validity",
            set(states)
            <= {
                "target_below_min_attacks",
                "match_pool_below_8",
                "match_pool_below_signal_capable",
                "evaluated",
            },
            dict(states),
            "허용 상태만",
            "관측 상태 집합",
        ),
        _check(
            "v3.rule_protocol",
            "consistency",
            all(row.get("rule_protocol_version") == rule_protocol for row in observations),
            dict(Counter(row.get("rule_protocol_version") for row in observations)),
            {rule_protocol: len(observations)},
            "모든 관측의 R2 이벤트 계약",
        ),
        _check(
            "v3.confidentiality",
            "confidentiality",
            leaked == 0,
            leaked,
            0,
            "Silver observation 원 player ID·이름 노출",
        ),
        _check(
            "v3.parsed_pseudonym",
            "confidentiality",
            pseudonymous_errors == 0,
            pseudonymous_errors,
            0,
            "Silver parsed key·account_id 검사",
        ),
    ]
