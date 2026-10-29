"""Execute the same registration, processing and read use cases on synthetic input."""

from .ports import Environment, Files
import hashlib
from pathlib import Path
from src.domain.serialization import stable_json
from src.domain.synthetic import r2_fixture


class Demo:
    def __init__(
        self, root, files: Files, environment: Environment, write_inputs, run_batch, report_batch
    ):
        self.root, self.files, self.environment = root, files, environment
        self.write_inputs, self.run_batch, self.report_batch = write_inputs, run_batch, report_batch

    def run(self, state_dir):
        state_dir = Path(state_dir)
        inputs = state_dir / "demo-inputs"
        fixture = self.files.read_json(self.root / "tests/fixtures/TESTMATCH.telemetry.json")
        manifest = self.write_inputs(inputs, [("TESTMATCH", fixture), ("R2MATCH", r2_fixture())])
        environment = self.environment.runtime()
        batch_id = (
            "demo-"
            + hashlib.sha256(
                stable_json(
                    [self.environment.fingerprint(), environment["python"], environment["sqlite"]]
                )
            ).hexdigest()[:12]
        )
        first = self.run_batch(batch_id, manifest, state_dir=state_dir, source_root=inputs)
        second = self.run_batch(batch_id, manifest, state_dir=state_dir, source_root=inputs)
        if (
            not first["complete"]
            or first["attempts"] != second["attempts"]
            or first["jobs"] != second["jobs"]
        ):
            raise RuntimeError("DEMO_REPLAY_FAILED")
        result = self.report_batch(batch_id, state_dir=state_dir)
        review = self.files.read_text(
            state_dir / "reports" / batch_id / "review-queue.md", encoding="utf-8"
        )
        if review.count("판정: **REVIEW**") != 3:
            raise RuntimeError("DEMO_SIGNAL_COUNT")
        return {
            "batch_id": batch_id,
            "complete": True,
            "jobs": result["counts"],
            "metrics": result["metrics"],
            "reused_without_new_attempts": True,
            "review_signals": 3,
            "report_dir": str(state_dir / "reports" / batch_id),
        }
