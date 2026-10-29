"""Hash the complete runtime tree, including nested implementations."""

import hashlib
from pathlib import Path

from src.domain.serialization import stable_json


def source_hashes(root: Path) -> dict[str, str]:
    paths = sorted([*(root / "src").rglob("*.py"), *(root / "sql").rglob("*.sql")])
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def fingerprint(root: Path) -> str:
    # Compatibility entry points alone cannot identify the implementation they call.
    return hashlib.sha256(stable_json(source_hashes(root))).hexdigest()
