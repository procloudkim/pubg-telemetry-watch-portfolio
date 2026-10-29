"""Manifest containment, checksum and telemetry decoding boundary."""

import hashlib
import json
from pathlib import Path
from .files import ROOT, read_checked_bytes, sha256_file, load_events_path
from src.domain.operations import PROTOCOLS
from src.domain.errors import OpsError
from src.domain.tokens import validate_token


def _artifact_path(root, artifact):
    relative = Path(artifact.get("path", ""))
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise OpsError("INPUT_PATH")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise OpsError("INPUT_PATH")
    if not path.is_file() or sha256_file(path) != artifact.get("sha256"):
        raise OpsError("INPUT_CHECKSUM")
    if path.stat().st_size != artifact.get("bytes"):
        raise OpsError("INPUT_BYTES")
    return path


def read_inputs(manifest_path, source_root=ROOT):
    body = manifest_path.read_bytes()
    manifest = json.loads(body)
    if (
        not isinstance(manifest, dict)
        or not isinstance(manifest.get("quality"), dict)
        or manifest["quality"].get("status") != "PASS"
    ):
        raise OpsError("INPUT_DQ_NOT_PASS")
    rule_protocol = PROTOCOLS.get(manifest.get("protocol_version"))
    if not rule_protocol or manifest.get("rule_protocol_version", rule_protocol) != rule_protocol:
        raise OpsError("INPUT_PROTOCOL")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or any(not isinstance(row, dict) for row in artifacts):
        raise OpsError("INPUT_ARTIFACTS")
    selections, metadata = {}, {}
    for artifact in artifacts:
        if artifact.get("dataset") == "match_selection":
            rows = json.loads(
                read_checked_bytes(
                    _artifact_path(source_root, artifact), artifact["sha256"]
                ).decode("utf-8")
            )
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise OpsError("INPUT_MATCH_METADATA")
            for row in rows:
                if row["match_id"] in selections:
                    raise OpsError("DUPLICATE_MATCH_METADATA")
                selections[row["match_id"]] = {
                    "mode": row.get("mode") or "unknown",
                    "map_name": row.get("map") or "unknown",
                }
        elif artifact.get("layer") == "bronze" and artifact.get("dataset") == "matches":
            metadata[Path(artifact["path"]).stem] = artifact
    inputs = []
    for artifact in artifacts:
        if artifact.get("layer") != "bronze" or artifact.get("dataset") not in {
            "telemetry",
            "telemetry_events",
        }:
            continue
        path = _artifact_path(source_root, artifact)
        match_id = path.name.removesuffix(".gz").removesuffix(".json")
        validate_token(match_id, "match_id")
        if type(artifact.get("records")) is not int or artifact["records"] <= 0:
            raise OpsError("INPUT_RECORD_COUNT")
        info = selections.get(match_id, {"mode": "unknown", "map_name": "unknown"})
        if match_id in metadata:
            artifact_metadata = metadata[match_id]
            match = json.loads(
                read_checked_bytes(
                    _artifact_path(source_root, artifact_metadata), artifact_metadata["sha256"]
                ).decode("utf-8")
            )
            if (
                not isinstance(match, dict)
                or not isinstance(match.get("data"), dict)
                or not isinstance(match["data"].get("attributes"), dict)
            ):
                raise OpsError("INPUT_MATCH_METADATA")
            if match["data"].get("id") != match_id:
                raise OpsError("INPUT_MATCH_ID")
            attrs = match["data"]["attributes"]
            info = {
                "mode": attrs.get("gameMode") or "unknown",
                "map_name": attrs.get("mapName") or "unknown",
            }
        with path.open("rb") as stream:
            encoding = "gzip" if stream.read(2) == b"\x1f\x8b" else "json"
        inputs.append(
            {
                "input_encoding": encoding,
                "match_id": match_id,
                "source_path": str(path),
                "source_sha256": artifact["sha256"],
                "source_bytes": artifact["bytes"],
                "source_records": artifact["records"],
                **info,
            }
        )
    if not inputs or len({row["match_id"] for row in inputs}) != len(inputs):
        raise OpsError("EMPTY_OR_DUPLICATE_MATCHES")
    return (
        hashlib.sha256(body).hexdigest(),
        rule_protocol,
        sorted(inputs, key=lambda row: row["match_id"]),
    )


class BatchInputs:
    read_inputs = staticmethod(read_inputs)

    def load(self, job):
        path = Path(job["source_path"])
        if path.stat().st_size != job["source_bytes"]:
            raise OpsError("INPUT_CHECKSUM")
        events = load_events_path(path, expected_sha256=job["source_sha256"])
        if len(events) != job["source_records"] or any(
            not isinstance(event, dict) for event in events
        ):
            raise OpsError("INPUT_EVENT_SCHEMA")
        return events
