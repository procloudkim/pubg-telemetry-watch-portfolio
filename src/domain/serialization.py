"""Canonical JSON and delimited hash contracts shared by existing artifacts."""

import hashlib
import json


def stable_json(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def digest(*parts):
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()
