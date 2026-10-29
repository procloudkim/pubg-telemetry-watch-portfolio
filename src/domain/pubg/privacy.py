"""Preserve the existing parsed-player identity projection."""

from ..identity import player_key


def _pseudonymous_parsed(parsed, run_id):
    players = {}
    for name, player in parsed["players"].items():
        key = player_key(run_id, name, player.get("account_id"))
        players[key] = {field: value for field, value in player.items() if field != "account_id"}
    return {
        "match_id": parsed["match_id"],
        "rule_protocol_version": parsed["rule_protocol_version"],
        "players": players,
        "event_count": parsed["event_count"],
    }
