"""Load graph audit inputs, project in memory, then publish checked output."""

from .ports import Files
from pathlib import Path
from src.domain.graph import project_run, required_match_ids, _check


class GraphAudit:
    def __init__(self, files: Files, render):
        self.files, self.render = files, render

    def load(self, path, expected_type):
        value = self.files.read_json(path)
        if not isinstance(value, expected_type):
            raise ValueError("graph 입력 JSON 최상위 형식 오류")
        return value

    def analyze_run(self, run_id, bronze, silver, manifest_path):
        cohort_path, observation_path = silver / "cohort.json", silver / "observations.json"
        cohort = self.load(cohort_path, dict)
        observations = self.load(observation_path, list)
        manifest = self.load(manifest_path, dict)
        match_dir = bronze / "api/matches"
        ids = required_match_ids(observations)
        paths = [match_dir / f"{match_id}.json" for match_id in ids]
        if any(not self.files.exists(path) for path in paths):
            raise ValueError("observation match metadata 누락")
        documents = [(path.name, self.files.hash(path), self.load(path, dict)) for path in paths]
        parsed = {
            match_id: self.load(silver / "parsed" / f"{match_id}.json", dict) for match_id in ids
        }
        hashes = {
            "cohort": self.files.hash(cohort_path),
            "observations": self.files.hash(observation_path),
            "manifest": self.files.hash(manifest_path),
        }
        return project_run(
            run_id,
            cohort,
            observations,
            manifest,
            documents,
            parsed,
            hashes,
            len(self.files.glob(match_dir, "*.json")),
        )

    def write_report(self, summary, raw_tokens, path: Path):
        summary["checks"].append(
            _check(
                "output.raw_identity", True, 0, 0, "보고서 원 playerId와 name 정확 문자열 교집합"
            )
        )
        summary["decision"] = (
            "FEASIBLE_FOR_NEO4J_REVIEW"
            if all(row["status"] == "PASS" for row in summary["checks"])
            else "STOP"
        )
        report = self.render(summary)
        leaked = {token for token in raw_tokens if len(token) >= 3 and token in report}
        summary["checks"][-1] = _check(
            "output.raw_identity",
            not leaked,
            len(leaked),
            0,
            "보고서 원 playerId와 name 정확 문자열 교집합",
        )
        summary["decision"] = (
            "FEASIBLE_FOR_NEO4J_REVIEW"
            if all(row["status"] == "PASS" for row in summary["checks"])
            else "STOP"
        )
        report = self.render(summary)
        if any(token in report for token in leaked):
            raise ValueError("graph 보고서 identity 검사 실패")
        self.files.write_bytes(path, report.encode("utf-8"))
        return report
