import unittest
from unittest.mock import patch

from src.detect import r3_kill_burst
from src.parse import LEGACY_RULE_PROTOCOL_VERSION, parse_match


class EventContextRulesTest(unittest.TestCase):
    def test_parser_filters_r2_events_and_uses_groggy_action_time(self):
        events = [
            {"_T": "LogPlayerAttack", "attackId": 1, "attacker": {"name": "target"}},
            {"_T": "LogPlayerAttack", "attackId": 2, "attacker": {"name": "target"}},
            {
                "_T": "LogPlayerTakeDamage",
                "attackId": 1,
                "damage": 12,
                "attacker": {"name": "target"},
            },
            {
                "_T": "LogPlayerTakeDamage",
                "attackId": 1,
                "damage": 0,
                "damageTypeCategory": "Damage_DBNO",
                "attacker": {"name": "target"},
            },
            {
                "_T": "LogPlayerTakeDamage",
                "attackId": 99,
                "damage": 4,
                "attacker": {"name": "target"},
            },
            {
                "_T": "LogPlayerMakeGroggy",
                "_D": "2026-01-01T00:00:10Z",
                "dBNOId": 7,
                "attacker": {"name": "target"},
            },
            {
                "_T": "LogPlayerKillV2",
                "_D": "2026-01-01T00:00:40Z",
                "dBNOId": 7,
                "killer": {"name": "target"},
                "dBNOMaker": {"name": "target"},
                "victim": {"type": "user_ai"},
            },
        ]
        with patch("src.adapters.files.LocalFiles.load_events", return_value=events):
            parsed = parse_match("match")
            legacy = parse_match("match", rule_protocol=LEGACY_RULE_PROTOCOL_VERSION)
        player = parsed["players"]["target"]
        self.assertEqual(player["damage_events"], 1)
        self.assertEqual(player["kills"], [player["kill_events"][0]["action_time"]])
        self.assertEqual(player["kill_events"][0]["time_source"], "make_groggy")
        self.assertEqual(legacy["players"]["target"]["damage_events"], 3)
        self.assertEqual(legacy["players"]["target"]["kill_events"][0]["time_source"], "kill_v2")

    def test_r3_uses_action_time_and_reports_ai_stratum(self):
        delayed = {
            "kills": [],
            "kill_events": [
                {
                    "action_time": action,
                    "kill_time": kill,
                    "time_source": "make_groggy",
                    "victim_type": "user_ai",
                }
                for action, kill in ((0, 30), (20, 31), (40, 32))
            ],
        }
        self.assertEqual(r3_kill_burst("target", delayed), [])
        direct = {
            "kills": [],
            "kill_events": [
                {
                    "action_time": value,
                    "kill_time": value,
                    "time_source": "kill_v2",
                    "victim_type": "user_ai",
                }
                for value in (0, 5, 10)
            ],
        }
        signal = r3_kill_burst("target", direct)[0]
        self.assertEqual(signal["victim_type_stratum"], "user_ai_only")
        self.assertEqual(signal["evidence"]["victim_type_counts"]["user_ai"], 3)


if __name__ == "__main__":
    unittest.main()
