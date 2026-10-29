import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.ops_demo import benchmark, compare_results, synthetic_results, write_inputs, r2_fixture
from src import ops
from src.adapters.environment import Environment
from contextlib import closing


class BenchmarkTest(unittest.TestCase):
    def test_external_memory_fresh_runs_and_cross_version_actor_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = benchmark(root / "bench", sizes=(1000,), repeats=1, match_events=500)
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row["new_success_events"], 1000)
                self.assertEqual(row["metrics"]["successful_duration_samples"], 2)
                self.assertGreater(row["run_peak_rss_kib"], 0)
                self.assertGreater(row["report_peak_rss_kib"], 0)
                self.assertAlmostEqual(row["events_per_second"], 1000 / row["total_seconds"])
                self.assertGreaterEqual(row["e2e_seconds"], row["total_seconds"])
            with self.assertRaisesRegex(RuntimeError, "OUTPUT_EXISTS"):
                benchmark(root / "bench", sizes=(1000,), repeats=1)
            manifest = write_inputs(root / "inputs", [("R2", r2_fixture())])
            results = []
            hashes = []
            for code in ("old", "new"):
                with patch.object(Environment, "fingerprint", return_value=code):
                    status = ops.run_batch(
                        code, manifest, state_dir=root / code, source_root=root / "inputs"
                    )
                    hashes.append(status["jobs"][0]["result_sha256"])
                with closing(ops.connect(root / code, readonly=True)) as connection:
                    results.append(synthetic_results(connection))
            self.assertNotEqual(*hashes)
            self.assertTrue(compare_results(*results))
            changed = json.loads(json.dumps(results[1]))
            changed[0]["signals"][0]["rule"] = "R1_speed"
            self.assertFalse(compare_results(results[0], changed))
            self.assertTrue(compare_results(1.0, 1.0 + 1e-10))
            self.assertFalse(compare_results(1.0, 1.01))


if __name__ == "__main__":
    unittest.main()
