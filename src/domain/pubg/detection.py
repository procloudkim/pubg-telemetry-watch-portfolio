"""Existing PUBG rules and observation semantics; no I/O."""

import hashlib
import math
import statistics
from .parsing import LEGACY_RULE_PROTOCOL_VERSION, RULE_PROTOCOLS

SPEED_MS = 8.5
SPEED_WINDOW_S = 5

Z_HIT = 3.0
MIN_ATTACKS = 30

MIN_R2_POOL = 8

MIN_R2_SIGNAL_POOL = math.floor(Z_HIT**2) + 2

KILL_N = 3
KILL_WINDOW_S = 12


def in_vehicle(t, spans):
    return any(a - 2 <= t <= b + 2 for a, b in spans)


def r1_speed(name, p):
    pos = p["positions"]
    out = []
    i = 0
    for j in range(len(pos)):
        while pos[j][0] - pos[i][0] > SPEED_WINDOW_S:
            i += 1
        t0, x0, y0 = pos[i]
        t1, x1, y1 = pos[j]
        dt = t1 - t0
        if dt < 2 or in_vehicle(t0, p["vehicle_spans"]) or in_vehicle(t1, p["vehicle_spans"]):
            continue
        v = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / dt
        if v > SPEED_MS:
            out.append(
                {
                    "rule": "R1_speed",
                    "player": name,
                    "value": round(v, 2),
                    "threshold": SPEED_MS,
                    "evidence": {
                        "t_start": round(t0, 1),
                        "t_end": round(t1, 1),
                        "from_m": [round(x0), round(y0)],
                        "to_m": [round(x1), round(y1)],
                    },
                }
            )
    return [max(out, key=lambda s: s["value"])] if out else []


def r2_hit_ratio(players):
    ratios, mean, sd = r2_context(players)
    if len(ratios) < MIN_R2_POOL:
        return []
    out = []
    for n, r in ratios.items():
        z = (r - mean) / sd
        if z > Z_HIT:
            out.append(
                {
                    "rule": "R2_hit_ratio",
                    "player": n,
                    "value": round(r, 3),
                    "threshold": f"z>{Z_HIT} (mean {mean:.3f}, sd {sd:.3f})",
                    "evidence": {
                        "attacks": players[n]["attacks"],
                        "damage_events": players[n]["damage_events"],
                        "z": round(z, 2),
                    },
                }
            )
    return out


def r2_context(players):
    ratios = {
        n: p["damage_events"] / p["attacks"]
        for n, p in players.items()
        if p["attacks"] >= MIN_ATTACKS
    }
    if not ratios:
        return ratios, None, None
    return ratios, statistics.mean(ratios.values()), statistics.pstdev(ratios.values()) or 1e-9


def r2_observation(players, *, account_id=None, name=None):
    """한 대상의 R2 상태를 배타적인 분석 상태로 반환한다."""
    if account_id:
        matches = [(n, p) for n, p in players.items() if p.get("account_id") == account_id]
        if len(matches) != 1:
            raise ValueError(f"target account 식별 실패: {len(matches)}명")
        name, player = matches[0]
    elif name in players:
        player = players[name]
    else:
        raise ValueError("target player 식별 실패")
    attacks = player["attacks"]
    damage_events = player["damage_events"]
    base = {
        "attacks": attacks,
        "damage_events": damage_events,
        "ratio": damage_events / attacks if attacks else None,
        "review_candidate": False,
        "minimum_signal_pool": MIN_R2_SIGNAL_POOL,
    }
    if attacks < MIN_ATTACKS:
        return {
            **base,
            "status": "target_below_min_attacks",
            "eligible_players": None,
            "match_mean": None,
            "match_sd": None,
            "local_z": None,
        }
    ratios, mean, sd = r2_context(players)
    if len(ratios) < MIN_R2_POOL:
        return {
            **base,
            "status": "match_pool_below_8",
            "eligible_players": len(ratios),
            "match_mean": mean,
            "match_sd": sd,
            "local_z": None,
        }
    if len(ratios) < MIN_R2_SIGNAL_POOL:
        return {
            **base,
            "status": "match_pool_below_signal_capable",
            "eligible_players": len(ratios),
            "match_mean": mean,
            "match_sd": sd,
            "local_z": None,
        }
    z = (ratios[name] - mean) / sd
    return {
        **base,
        "status": "evaluated",
        "eligible_players": len(ratios),
        "match_mean": mean,
        "match_sd": sd,
        "local_z": z,
        "review_candidate": z > Z_HIT,
    }


def r3_kill_burst(name, p):
    events = p.get("kill_events") or [
        {"action_time": value, "kill_time": value, "time_source": "kill_v2", "victim_type": None}
        for value in p["kills"]
    ]
    events = sorted(
        (row for row in events if isinstance(row.get("action_time"), (int, float))),
        key=lambda row: row["action_time"],
    )
    for i in range(len(events) - KILL_N + 1):
        window = events[i : i + KILL_N]
        if window[-1]["action_time"] - window[0]["action_time"] <= KILL_WINDOW_S:
            types = [row.get("victim_type") for row in window]
            counts = {
                "user_ai": sum(value == "user_ai" for value in types),
                "non_user_ai": sum(value not in (None, "user_ai") for value in types),
                "unknown": sum(value is None for value in types),
            }
            present = [key for key, value in counts.items() if value]
            stratum = (
                {
                    "user_ai": "user_ai_only",
                    "non_user_ai": "non_user_ai_only",
                    "unknown": "unknown",
                }.get(present[0])
                if len(present) == 1
                else "mixed"
            )
            return [
                {
                    "rule": "R3_kill_burst",
                    "player": name,
                    "value": KILL_N,
                    "threshold": f"{KILL_N} kills/{KILL_WINDOW_S}s",
                    "victim_type_stratum": stratum,
                    "evidence": {
                        "action_times": [round(row["action_time"], 1) for row in window],
                        "kill_times": [round(row["kill_time"], 1) for row in window],
                        "time_sources": [row["time_source"] for row in window],
                        "victim_type_counts": counts,
                    },
                }
            ]
    return []


def mask_signals(signals):
    return [
        {
            **row,
            "player": "pla***",
            "player_key": hashlib.sha256(f"{row['match_id']}|{row['player']}".encode()).hexdigest()[
                :24
            ],
        }
        for row in signals
    ]


def detect_match(parsed):
    protocol = parsed.get("rule_protocol_version", LEGACY_RULE_PROTOCOL_VERSION)
    if protocol not in RULE_PROTOCOLS:
        raise ValueError("parsed rule protocol 불일치")
    signals = []
    for name, player in parsed["players"].items():
        signals += r1_speed(name, player) + r3_kill_burst(name, player)
    signals += r2_hit_ratio(parsed["players"])
    for signal in signals:
        if signal["rule"] == "R2_hit_ratio":
            signal["evidence"]["event_filter"] = (
                "all_attributed_events"
                if protocol == LEGACY_RULE_PROTOCOL_VERSION
                else "damage>0+matching_attackId"
            )
        signal.update(match_id=parsed["match_id"], rule_protocol_version=protocol)
    return signals
