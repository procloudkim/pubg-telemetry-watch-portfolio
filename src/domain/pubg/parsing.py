"""PUBG event interpretation for the frozen rule protocols; no I/O."""

from datetime import datetime

RULE_PROTOCOL_VERSION = "rules-event-context-2"

LEGACY_RULE_PROTOCOL_VERSION = "rules-event-count-1"

RULE_PROTOCOLS = (LEGACY_RULE_PROTOCOL_VERSION, RULE_PROTOCOL_VERSION)


def ts(ev):
    return datetime.fromisoformat(ev["_D"].replace("Z", "+00:00")).timestamp()


def parse_events(match_id, events, *, rule_protocol=RULE_PROTOCOL_VERSION):
    if rule_protocol not in RULE_PROTOCOLS:
        raise ValueError(f"알 수 없는 rule protocol: {rule_protocol}")
    players = {}
    groggy_times = {}

    def player_for(name, account_id=None):
        player = players.setdefault(
            name,
            {
                "account_id": account_id,
                "positions": [],
                "vehicle_spans": [],
                "_veh": None,
                "attacks": 0,
                "_attack_ids": set(),
                "_damage_candidates": [],
                "damage_events": 0,
                "damage_dealt": 0.0,
                "kills": [],
                "kill_events": [],
                "headshot_kills": 0,
            },
        )
        if account_id and not player["account_id"]:
            player["account_id"] = account_id
        return player

    for ev in events:
        t = ev.get("_T")
        if t == "LogPlayerPosition":
            ch = ev.get("character") or {}
            if ch.get("name"):
                loc = ch.get("location") or {}
                player_for(ch["name"], ch.get("accountId"))["positions"].append(
                    (ts(ev), loc.get("x", 0) / 100, loc.get("y", 0) / 100)
                )
        elif t == "LogVehicleRide":
            ch = ev.get("character") or {}
            if ch.get("name"):
                player_for(ch["name"], ch.get("accountId"))["_veh"] = ts(ev)
        elif t == "LogVehicleLeave":
            ch = ev.get("character") or {}
            if ch.get("name"):
                p = player_for(ch["name"], ch.get("accountId"))
                if p["_veh"] is not None:
                    p["vehicle_spans"].append((p["_veh"], ts(ev)))
                    p["_veh"] = None
        elif t == "LogPlayerAttack":
            at = ev.get("attacker") or {}
            if at.get("name"):
                p = player_for(at["name"], at.get("accountId"))
                p["attacks"] += 1
                if ev.get("attackId") is not None:
                    p["_attack_ids"].add(ev["attackId"])
        elif t == "LogPlayerTakeDamage":
            at = ev.get("attacker") or {}
            if at.get("name"):
                p = player_for(at["name"], at.get("accountId"))
                damage = float(ev.get("damage") or 0)
                p["damage_dealt"] += damage
                if rule_protocol == LEGACY_RULE_PROTOCOL_VERSION:
                    p["damage_events"] += 1
                else:
                    p["_damage_candidates"].append((ev.get("attackId"), damage))
        elif t == "LogPlayerMakeGroggy":
            at = ev.get("attacker") or {}
            dbno_id = ev.get("dBNOId")
            if at.get("name") and dbno_id not in (None, -1, 0):
                player_for(at["name"], at.get("accountId"))
                groggy_times[(dbno_id, at["name"])] = ts(ev)
        elif t == "LogPlayerKillV2":
            kl = ev.get("killer") or {}
            if kl.get("name"):
                p = player_for(kl["name"], kl.get("accountId"))
                kill_time = ts(ev)
                action_time, time_source = kill_time, "kill_v2"
                if rule_protocol == RULE_PROTOCOL_VERSION:
                    dbno_id = ev.get("dBNOId")
                    maker = ev.get("dBNOMaker") or {}
                    if dbno_id not in (None, -1, 0) and maker.get("name") == kl["name"]:
                        action_time = groggy_times.get((dbno_id, kl["name"]))
                        time_source = (
                            "make_groggy" if action_time is not None else "missing_make_groggy"
                        )
                    elif dbno_id not in (None, -1, 0):
                        time_source = "kill_v2_finisher"
                if action_time is not None:
                    p["kills"].append(action_time)
                p["kill_events"].append(
                    {
                        "action_time": action_time,
                        "kill_time": kill_time,
                        "time_source": time_source,
                        "victim_type": (ev.get("victim") or {}).get("type"),
                    }
                )
                dr = str(
                    ev.get("damageReason")
                    or (ev.get("killerDamageInfo") or {}).get("damageReason", "")
                )
                if "HeadShot" in dr:
                    p["headshot_kills"] += 1
    for p in players.values():
        if rule_protocol == RULE_PROTOCOL_VERSION:
            p["damage_events"] = sum(
                damage > 0 and attack_id in p["_attack_ids"]
                for attack_id, damage in p["_damage_candidates"]
            )
        if p["_veh"] is not None and p["positions"]:
            p["vehicle_spans"].append((p["_veh"], p["positions"][-1][0]))
        del p["_veh"], p["_attack_ids"], p["_damage_candidates"]
    return {
        "match_id": match_id,
        "rule_protocol_version": rule_protocol,
        "players": players,
        "event_count": len(events),
    }
