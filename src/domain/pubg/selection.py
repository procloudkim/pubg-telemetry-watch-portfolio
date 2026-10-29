"""PUBG selection and asset interpretation without transport access."""


def current_season(payload):
    for row in payload.get("data", []):
        if (row.get("attributes") or {}).get("isCurrentSeason"):
            return row["id"]
    raise SystemExit("현재 시즌을 찾지 못함")


def top_players(payload, limit):
    players = [row for row in payload.get("included", []) if row.get("type") == "player"]
    players.sort(key=lambda row: (row.get("attributes") or {}).get("rank", 10**9))
    return players[:limit]


def round_robin_matches(match_ids_by_player, per_player):
    selected = []
    seen = set()
    for index in range(per_player):
        for match_ids in match_ids_by_player.values():
            if index < len(match_ids) and match_ids[index] not in seen:
                seen.add(match_ids[index])
                selected.append(match_ids[index])
    return selected


def telemetry_url(match):
    for item in match.get("included", []):
        if item.get("type") == "asset" and (item.get("attributes") or {}).get("URL"):
            return item["attributes"]["URL"]
    raise ValueError("match 응답에 telemetry asset URL 없음")
