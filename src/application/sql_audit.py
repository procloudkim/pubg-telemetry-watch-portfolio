"""Verify audit inputs, compare SQL and Python read models, then publish."""

from .ports import AuditEngine, Files
import json
from pathlib import Path
from src.domain.audit import _cross_check
from src.domain.tokens import validate_token


class SqlAudit:
    def __init__(self, files: Files, engine: AuditEngine, render):
        self.files, self.engine, self.render = files, engine, render

    def _load_json(self, path: Path, expected_type, expected_sha256=None):
        body = (
            self.files.read_checked_bytes(path, expected_sha256)
            if expected_sha256 is not None
            else self.files.read_bytes(path)
        )
        value = json.loads(body)
        if not isinstance(value, expected_type):
            raise ValueError(f"JSON 최상위 형식 오류: {path.name}")
        return value

    def _artifact(self, manifest, dataset):
        matches = [row for row in manifest.get("artifacts", []) if row.get("dataset") == dataset]
        if len(matches) != 1:
            raise ValueError(f"manifest dataset은 정확히 1개여야 함: {dataset}={len(matches)}")
        return matches[0]

    def _artifact_path(self, root: Path, artifact):
        relative = Path(artifact.get("path", ""))
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise ValueError("manifest artifact 상대 경로 오류")
        path = self.files.resolve(root / relative)
        if not path.is_relative_to(self.files.resolve(root)):
            raise ValueError("manifest artifact 상대 경로 오류")
        if not self.files.is_file(path) or self.files.hash(path) != artifact.get("sha256"):
            raise RuntimeError(f"소비 artifact checksum 불일치: {relative.as_posix()}")
        return path

    def read(self, run_id, root, sql_path):
        validate_token(run_id, "--run-id")
        manifest_path = root / "data" / "manifests" / "v3" / f"{run_id}.json"
        manifest = self._load_json(manifest_path, dict)
        if (
            manifest.get("dataset_version") != "v3"
            or manifest.get("run_id") != run_id
            or (manifest.get("quality") or {}).get("status") != "PASS"
            or not isinstance(manifest.get("protocol_version"), str)
        ):
            raise RuntimeError("v3 manifest identity 또는 DQ 상태 오류")
        observation_artifact = self._artifact(manifest, "r2_observations")
        validation_artifact = self._artifact(manifest, "holdout_validation")
        observation_path = self._artifact_path(root, observation_artifact)
        validation_path = self._artifact_path(root, validation_artifact)
        # Verify the consumed bytes as well as the earlier manifest inspection.
        observations = self._load_json(observation_path, list, observation_artifact["sha256"])
        validation = self._load_json(validation_path, dict, validation_artifact["sha256"])
        if (
            validation.get("run_id") != run_id
            or validation.get("protocol_version") != manifest["protocol_version"]
        ):
            raise RuntimeError("Gold validation identity 불일치")
        if any(
            not isinstance(row, dict) or "player_key" not in row or "player" in row or "name" in row
            for row in observations
        ):
            raise RuntimeError("Silver observation 비식별 schema 오류")
        source_hashes = {
            "manifest": self.files.hash(manifest_path),
            "observations": observation_artifact["sha256"],
            "validation": validation_artifact["sha256"],
        }
        summary = self.engine.calculate(run_id, manifest, observations, source_hashes, sql_path)
        summary["checks"] = _cross_check(summary, validation, manifest)
        return summary

    def audit_run(self, run_id, *, root, sql_path, report_path=None):
        summary = self.read(run_id, root, sql_path)
        target = report_path or root / "reports/sql-audit.md"
        self.files.write_bytes(target, self.render(summary).encode("utf-8"))
        return summary
