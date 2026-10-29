"""Fixed-seed synthetic actors and version-independent parity; not service capacity evidence."""

from datetime import datetime, timedelta, timezone
import math
import random


def r2_fixture(pool=11, attacks=30):
    events = []
    for player in range(pool):
        actor = {"name": f"synthetic_{player}", "accountId": f"synthetic-id-{player}"}
        for attack in range(attacks):
            events.append({"_T": "LogPlayerAttack", "attackId": attack, "attacker": actor})
        for index in range(90 if player == 0 else 3):
            events.append(
                {
                    "_T": "LogPlayerTakeDamage",
                    "attackId": index % max(attacks, 1),
                    "damage": 1,
                    "attacker": actor,
                }
            )
    if pool:
        actor = {"name": "synthetic_0", "accountId": "synthetic-id-0"}
        events += [
            {"_T": "LogPlayerAttack", "attackId": 0, "attacker": actor},
            {"_T": "LogPlayerTakeDamage", "attackId": 0, "damage": 0, "attacker": actor},
            {"_T": "LogPlayerTakeDamage", "attackId": 99999, "damage": 1, "attacker": actor},
            {"_T": "LogPlayerTakeDamage", "attackId": None, "damage": 1, "attacker": actor},
        ]
    return events


def load_matches(total_events, *, seed=20260909, match_events=40000):
    """60% 위치 / 20% 공격 / 20% 피해의 합성 workload. 매치당 100명, 동일 최대 크기."""
    rng = random.Random(seed)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index, offset in enumerate(range(0, total_events, match_events)):
        events = []
        last_attack = {}
        actors = [{"name": f"synthetic_{p}", "accountId": f"synthetic-id-{p}"} for p in range(100)]
        for ordinal in range(min(match_events, total_events - offset)):
            player, seconds = ordinal % 100, ordinal // 100
            actor = actors[player]
            when = (base + timedelta(seconds=seconds)).isoformat()
            kind = rng.randrange(100)
            if kind < 60:
                event = {
                    "_T": "LogPlayerPosition",
                    "_D": when,
                    "character": {**actor, "location": {"x": seconds * 400, "y": 0}},
                }
            elif kind < 80:
                last_attack[player] = ordinal
                event = {
                    "_T": "LogPlayerAttack",
                    "_D": when,
                    "attackId": ordinal,
                    "attacker": actor,
                }
            else:
                event = {
                    "_T": "LogPlayerTakeDamage",
                    "_D": when,
                    "attackId": last_attack.get(player),
                    "attacker": actor,
                    "damage": 0 if ordinal % 10 == 0 else 1,
                }
            events.append(event)
        yield f"LOAD{index:06d}", events


def compare_results(left, right):
    if isinstance(left, float) and isinstance(right, (float, int)):
        return math.isfinite(right) and math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(compare_results(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(compare_results(a, b) for a, b in zip(left, right))
    return type(left) is type(right) and left == right
