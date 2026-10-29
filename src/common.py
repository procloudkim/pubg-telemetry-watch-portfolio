"""Compatibility exports for file and HTTP resources."""

from .adapters.files import (
    ROOT,
    DATA,
    REPORTS,
    BRONZE,
    SILVER,
    GOLD,
    MANIFESTS,
    OpsError,
    read_checked_bytes,
    atomic_write_bytes,
    atomic_write_json,
    sha256_file,
    write_once,
    telemetry_path,
    load_events,
    load_events_path,
)

from .domain.identity import player_key
from .adapters.credentials import API, api_key


def api_get(path: str, raw_path=None):
    from .cli.research_composition import collection

    return collection().http.get(path, raw_path)
