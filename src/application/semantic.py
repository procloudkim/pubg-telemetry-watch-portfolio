"""Coordinate immutable inputs, independent audit oracles and semantic publication."""

from .ports import Files, SemanticEngine
import hashlib
import json
import re
from pathlib import Path
from src.domain.errors import SemanticConformanceError
from src.domain.tokens import validate_token
from src.domain.serialization import stable_json
from src.domain.semantic import (
    ONTOLOGY_VERSION,
    ONTOLOGY_IRI,
    _resolve_protocols,
)

SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _hash(body):
    return hashlib.sha256(body).hexdigest()


class SemanticAudit:
    def __init__(self, files: Files, engine: SemanticEngine, graph_audit, sql_audit):
        self.files, self.engine = files, engine
        self.graph_audit, self.sql_audit = graph_audit, sql_audit

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

    def _safe_path(
        self, root: Path, relative_value: str, cache: dict[str, Path] | None = None
    ) -> Path:
        if not isinstance(relative_value, str) or not relative_value:
            raise ValueError("artifact 상대 경로 오류")
        relative = Path(relative_value)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("artifact 상대 경로 오류")
        if cache is not None and relative_value in cache:
            return cache[relative_value]
        root_resolved = root if root.is_absolute() else self.files.resolve(root)
        target = self.files.resolve(root / relative)
        if not target.is_relative_to(root_resolved):
            raise ValueError("artifact 경로가 저장소 밖을 가리킴")
        if cache is not None:
            cache[relative_value] = target
        return target

    def _relative(self, root: Path, path: Path) -> str:
        return self.files.resolve(path).relative_to(self.files.resolve(root)).as_posix()

    def _artifact_by_dataset(self, manifest: dict, dataset: str) -> dict:
        rows = [row for row in manifest["artifacts"] if row.get("dataset") == dataset]
        if len(rows) != 1:
            raise ValueError(f"manifest dataset 수 오류: {dataset}={len(rows)}")
        return rows[0]

    def _load_sources(self, root: Path, run_id: str) -> dict:
        validate_token(run_id, "run-id")
        root = self.files.resolve(root)
        path_cache: dict[str, Path] = {}
        manifest_path = root / "data/manifests/v3" / f"{run_id}.json"
        manifest = self._load_json(manifest_path, dict)
        if (
            manifest.get("schema_version") != 1
            or manifest.get("dataset_version") != "v3"
            or manifest.get("run_id") != run_id
            or ((manifest.get("quality") or {}).get("status") != "PASS")
        ):
            raise RuntimeError("v3 Manifest identity 또는 DQ 상태 오류")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError("manifest artifact 형식 오류")
        paths = [row.get("path") for row in artifacts if isinstance(row, dict)]
        if len(paths) != len(artifacts) or len(paths) != len(set(paths)):
            raise ValueError("manifest artifact 경로 중복 또는 누락")
        artifacts_by_path = {}
        for row in artifacts:
            path = self._safe_path(root, row.get("path"), path_cache)
            if not self.files.is_file(path):
                raise RuntimeError(f"manifest artifact 누락: {row['path']}")
            if (
                not isinstance(row.get("bytes"), int)
                or row["bytes"] < 0
                or self.files.stat(path).st_size != row["bytes"]
            ):
                raise RuntimeError(f"manifest artifact byte 불일치: {row['path']}")
            if not isinstance(row.get("sha256"), str) or not SHA256.fullmatch(row["sha256"]):
                raise ValueError(f"manifest artifact hash 형식 오류: {row['path']}")
            if self.files.hash(path) != row["sha256"]:
                raise RuntimeError(f"manifest artifact checksum 불일치: {row['path']}")
            if (
                row.get("layer") not in {"bronze", "silver", "gold"}
                or not isinstance(row.get("dataset"), str)
                or (not isinstance(row.get("media_type"), str))
                or (not isinstance(row.get("records"), int))
                or (row["records"] < 0)
                or (not isinstance(row.get("derived_from"), list))
            ):
                raise ValueError(f"manifest artifact metadata 오류: {row['path']}")
            for source in row["derived_from"]:
                source_path = self._safe_path(root, source, path_cache)
                if not self.files.is_file(source_path):
                    raise RuntimeError(f"lineage source 누락: {source}")
            artifacts_by_path[row["path"]] = {**row, "resolved_path": path}
        cohort_row = self._artifact_by_dataset(manifest, "frozen_cohort")
        observation_row = self._artifact_by_dataset(manifest, "r2_observations")
        validation_row = self._artifact_by_dataset(manifest, "holdout_validation")
        protocol_suffix = f"data/bronze/v3/{run_id}/protocol.json"
        protocol_rows = [row for row in artifacts if row.get("path") == protocol_suffix]
        if len(protocol_rows) != 1:
            raise ValueError("manifest protocol artifact 수 오류")
        return {
            "root": root,
            "run_id": run_id,
            "manifest": manifest,
            "manifest_path": manifest_path,
            "manifest_sha256": self.files.hash(manifest_path),
            "artifacts_by_path": artifacts_by_path,
            "cohort": self._load_json(
                artifacts_by_path[cohort_row["path"]]["resolved_path"], dict, cohort_row["sha256"]
            ),
            "cohort_path": artifacts_by_path[cohort_row["path"]]["resolved_path"],
            "observations": self._load_json(
                artifacts_by_path[observation_row["path"]]["resolved_path"],
                list,
                observation_row["sha256"],
            ),
            "observation_path": artifacts_by_path[observation_row["path"]]["resolved_path"],
            "gold": self._load_json(
                artifacts_by_path[validation_row["path"]]["resolved_path"],
                dict,
                validation_row["sha256"],
            ),
            "gold_path": artifacts_by_path[validation_row["path"]]["resolved_path"],
            "protocol": self._load_json(
                artifacts_by_path[protocol_suffix]["resolved_path"],
                dict,
                protocol_rows[0]["sha256"],
            ),
            "bronze": root / "data/bronze/v3" / run_id,
            "silver": root / "data/silver/v3" / run_id,
        }

    def _write_failure(self, root: Path, run_id: str, payload: dict) -> None:
        path = root / "reports" / f"semantic-validation-{run_id}.json"
        self.files.write_bytes(path, stable_json(payload))

    def build_sidecar(self, run_id, *, root):
        root = Path(root)
        sources = self._load_sources(root, run_id)
        contract = self.engine.load_contract(root)
        experiment, rule, season = _resolve_protocols(sources)
        stage = "graph"
        try:
            graph_summary, oracle_tokens = self.graph_audit.analyze_run(
                run_id, sources["bronze"], sources["silver"], sources["manifest_path"]
            )
            failed_oracle = [row["id"] for row in graph_summary["checks"] if row["status"] != "PASS"]
            if failed_oracle:
                raise SemanticConformanceError(f"기존 graph DQ 실패: {', '.join(failed_oracle)}")
            stage = "sql"
            try:
                sql_summary = self.sql_audit.read(run_id, root, root / "sql/v3_audit.sql")
            except RuntimeError as error:
                raise SemanticConformanceError(str(error)) from error
            stage = "semantic"
            result = self.engine.evaluate(
                run_id,
                sources,
                contract,
                experiment,
                rule,
                season,
                graph_summary,
                sql_summary,
                oracle_tokens,
            )
        except SemanticConformanceError as error:
            if error.report is None:
                error.report = {
                    "schema_version": 1,
                    "run_id": run_id,
                    "ontology_version": ONTOLOGY_VERSION,
                    "conforms": False,
                    "stage": stage,
                }
            self._write_failure(root, run_id, error.report)
            raise
        body, compressed, validation, checks = (
            result[key] for key in ("body", "compressed", "validation", "checks")
        )
        graph_path = root / "data/gold/v3" / run_id / "semantic.nt.gz"
        validation_path = root / "data/gold/v3" / run_id / "semantic-validation.json"
        semantic_manifest_path = root / "data/manifests/semantic/v3" / f"{run_id}.json"
        validation_body = stable_json(validation)
        self.files.write_once(graph_path, compressed)
        self.files.write_once(validation_path, validation_body)
        graph_relative = self._relative(root, graph_path)
        validation_relative = self._relative(root, validation_path)
        manifest_relative = self._relative(root, sources["manifest_path"])
        ontology_relative = self._relative(root, contract["ontology_path"])
        release_relative = self._relative(root, contract["release_path"])
        shapes_relative = self._relative(root, contract["shapes_path"])
        query_contract = [
            {
                "id": query_id,
                "path": self._relative(root, query["path"]),
                "sha256": self.files.hash(query["path"]),
            }
            for query_id, query in contract["queries"].items()
        ]
        semantic_manifest = {
            "schema_version": 1,
            "dataset_version": "semantic-v1",
            "run_id": run_id,
            "protocol_version": experiment,
            "rule_protocol_version": rule,
            "source_manifest": {"path": manifest_relative, "sha256": sources["manifest_sha256"]},
            "ontology": {
                "iri": ONTOLOGY_IRI,
                "version": ONTOLOGY_VERSION,
                "path": ontology_relative,
                "sha256": self.files.hash(contract["ontology_path"]),
                "version_path": release_relative,
                "version_sha256": self.files.hash(contract["release_path"]),
                "shapes_path": shapes_relative,
                "shapes_sha256": self.files.hash(contract["shapes_path"]),
                "queries": query_contract,
            },
            "runtime": self.engine.runtime(),
            "artifacts": [
                {
                    "layer": "gold",
                    "dataset": "semantic_graph",
                    "path": graph_relative,
                    "media_type": "application/n-triples",
                    "source_encoding": "gzip",
                    "bytes": len(compressed),
                    "records": result["triples"],
                    "sha256": _hash(compressed),
                    "uncompressed_sha256": _hash(body),
                    "derived_from": [manifest_relative, ontology_relative, shapes_relative],
                },
                {
                    "layer": "gold",
                    "dataset": "semantic_validation",
                    "path": validation_relative,
                    "media_type": "application/json",
                    "bytes": len(validation_body),
                    "records": 1,
                    "sha256": _hash(validation_body),
                    "derived_from": [
                        graph_relative,
                        shapes_relative,
                        *[row["path"] for row in query_contract],
                    ],
                },
            ],
            "quality": {"status": "PASS", "error_count": 0, "checks": checks},
        }
        self.files.write_once(semantic_manifest_path, stable_json(semantic_manifest))
        self.files.unlink(root / "reports" / f"semantic-validation-{run_id}.json", missing_ok=True)
        return semantic_manifest
