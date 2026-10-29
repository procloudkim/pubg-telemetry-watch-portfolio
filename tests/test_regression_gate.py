import json
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import src.detect as detect
import src.parse as parse
import src.report as report


FIXTURE = Path(__file__).parent / "fixtures" / "TESTMATCH.telemetry.json"


class RegressionGateTest(unittest.TestCase):
    def test_parse_detect_report_exact_expectations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"
            gold = data / "gold"
            reports = root / "reports"
            data.mkdir()
            (data / "TESTMATCH.telemetry.json").write_bytes(FIXTURE.read_bytes())
            (data / "manifest.json").write_text(
                json.dumps(
                    [
                        {
                            "match_id": "TESTMATCH",
                            "mode": "synthetic",
                            "map": "synthetic",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            path_patches = (patch("src.cli.research_composition.ROOT", root),)
            with ExitStack() as stack:
                for active_patch in path_patches:
                    stack.enter_context(active_patch)
                with patch.object(sys, "argv", ["parse", "--match", "TESTMATCH"]):
                    parse.main()
                with patch.object(sys, "argv", ["detect", "--match", "TESTMATCH"]):
                    detect.main()
                with patch.object(sys, "argv", ["report", "--match", "TESTMATCH"]):
                    report.main()

            parsed = json.loads((data / "TESTMATCH.parsed.json").read_text(encoding="utf-8"))
            self.assertEqual(set(parsed["players"]), {"normal_A", "fast_B", "driver_C", "burst_D"})
            signals = json.loads((data / "signals.json").read_text(encoding="utf-8"))
            self.assertEqual(
                Counter((row["player"], row["rule"]) for row in signals),
                Counter(
                    {
                        ("fast_B", "R1_speed"): 1,
                        ("burst_D", "R3_kill_burst"): 1,
                    }
                ),
            )

            gold_signals = json.loads((gold / "v1" / "signals.json").read_text(encoding="utf-8"))
            self.assertEqual([row["player"] for row in gold_signals], ["pla***", "pla***"])
            report_text = (reports / "review-queue.md").read_text(encoding="utf-8")
            self.assertEqual(report_text.count("판정: **REVIEW**"), 2)
            self.assertIn("매치 수: **1판**", report_text)
            self.assertIn("`synthetic` 1판", report_text)
            for raw_name in ("normal_A", "fast_B", "driver_C", "burst_D"):
                self.assertNotIn(raw_name, report_text)


if __name__ == "__main__":
    unittest.main()
