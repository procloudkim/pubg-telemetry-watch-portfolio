import sys
import unittest
from unittest.mock import patch

from src.elite import current_season, main, round_robin_matches, top_players


class EliteHelpersTest(unittest.TestCase):
    def test_selection_and_order(self):
        self.assertEqual(
            current_season(
                {
                    "data": [
                        {"id": "old", "attributes": {"isCurrentSeason": False}},
                        {"id": "now", "attributes": {"isCurrentSeason": True}},
                    ]
                }
            ),
            "now",
        )
        payload = {
            "included": [
                {"type": "player", "id": "p2", "attributes": {"rank": 2}},
                {"type": "player", "id": "p1", "attributes": {"rank": 1}},
                {"type": "asset", "id": "x", "attributes": {}},
            ]
        }
        self.assertEqual([row["id"] for row in top_players(payload, 2)], ["p1", "p2"])
        self.assertEqual(
            round_robin_matches({"p1": ["a", "shared"], "p2": ["b", "shared"]}, 2),
            ["a", "b", "shared"],
        )

    def test_api_call_limit_above_session_cap_is_rejected_before_request(self):
        with (
            patch.object(sys, "argv", ["elite", "--api-call-limit", "61"]),
            patch("src.adapters.http.PubgHttp.get") as api_get,
        ):
            with self.assertRaisesRegex(SystemExit, "3~60"):
                main()
        api_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
