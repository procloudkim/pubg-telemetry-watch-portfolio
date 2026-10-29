"""Write immutable synthetic telemetry input bundles."""

import gzip
import hashlib
from .files import write_once, sha256_file
from src.domain.serialization import stable_json


def write_inputs(root, matches, *, protocol="v1-rules-event-context-2", compressed=False):
    root.mkdir(parents=True, exist_ok=True)
    artifacts, selection = [], []
    for match_id, events in matches:
        body = stable_json(events)
        if compressed:
            body = gzip.compress(body, compresslevel=1, mtime=0)
        path = root / "telemetry" / (match_id + (".json.gz" if compressed else ".json"))
        write_once(path, body)
        artifacts.append(
            {
                "path": path.relative_to(root).as_posix(),
                "layer": "bronze",
                "dataset": "telemetry_events",
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
                "records": len(events),
                "source_encoding": "gzip" if compressed else "json",
                "derived_from": [],
            }
        )
        selection.append({"match_id": match_id, "mode": "synthetic", "map": "synthetic"})
    path = root / "selection.json"
    write_once(path, stable_json(selection))
    artifacts.append(
        {
            "path": "selection.json",
            "layer": "silver",
            "dataset": "match_selection",
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "records": len(selection),
            "derived_from": [],
        }
    )
    manifest = {
        "schema_version": 1,
        "dataset_version": "synthetic",
        "protocol_version": protocol,
        "artifacts": artifacts,
        "quality": {"status": "PASS"},
        "source": "synthetic; no external labels",
    }
    path = root / "manifest.json"
    write_once(path, stable_json(manifest))
    return path
