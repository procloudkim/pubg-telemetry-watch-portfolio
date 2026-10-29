"""Local files, immutable caches and durable ledger writes."""

from src.domain.errors import (
    OpsError,
)
import gzip
import hashlib
import json
import os
import pathlib
import tempfile
import shutil
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
BRONZE = DATA / "bronze"
SILVER = DATA / "silver"
GOLD = DATA / "gold"
MANIFESTS = DATA / "manifests"


def read_checked_bytes(path: pathlib.Path, expected_sha256: str) -> bytes:
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != expected_sha256:
        raise OpsError("INPUT_CHECKSUM")
    return body


def atomic_write_bytes(path: pathlib.Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_json(path: pathlib.Path, value, *, indent=None) -> None:
    body = json.dumps(value, ensure_ascii=False, indent=indent).encode()
    atomic_write_bytes(path, body)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_once(path: pathlib.Path, body: bytes) -> None:
    """Bronze cache: 같은 byte는 재사용하고 다른 byte의 덮어쓰기는 거부한다."""
    if path.exists():
        if sha256_file(path) != hashlib.sha256(body).hexdigest():
            display = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
            raise RuntimeError(f"write-once 내용 불일치: {display}")
        return
    atomic_write_bytes(path, body)


def telemetry_path(
    match_id: str, version: str | None = None, run_id: str | None = None
) -> pathlib.Path:
    bases = []
    if version:
        base = BRONZE / version
        if run_id:
            base /= run_id
        bases.append(base / "telemetry")
    else:
        bases.extend((BRONZE / name / "telemetry" for name in ("v1", "v2")))
    for base in bases:
        for suffix in (".json.gz", ".json"):
            candidate = base / f"{match_id}{suffix}"
            if candidate.exists():
                return candidate
    legacy = DATA / f"{match_id}.telemetry.json"
    if legacy.exists():
        return legacy
    raise FileNotFoundError(f"telemetry 없음: {match_id}")


def load_events(match_id: str, version: str | None = None, run_id: str | None = None) -> list:
    return load_events_path(telemetry_path(match_id, version, run_id))


def load_events_path(path: pathlib.Path, *, expected_sha256=None) -> list:
    body = (
        read_checked_bytes(path, expected_sha256)
        if expected_sha256 is not None
        else path.read_bytes()
    )
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    events = json.loads(body)
    if not isinstance(events, list):
        raise ValueError("telemetry 최상위가 배열이 아님")
    return events


class LocalFiles:
    def __init__(self, root=ROOT):
        self.root = root

    read_checked_bytes = staticmethod(read_checked_bytes)

    def write_bytes(self, path, body):
        atomic_write_bytes(path, body)

    write_json = staticmethod(atomic_write_json)
    hash = staticmethod(sha256_file)

    def write_once(self, path, body):
        write_once(path, body)

    def read_bytes(self, path):
        return path.read_bytes()

    def read_json(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def exists(self, path):
        return path.exists()

    def glob(self, path, pattern):
        return sorted(path.glob(pattern))

    def unlink(self, path, *, missing_ok=True):
        path.unlink(missing_ok=missing_ok)

    def read_text(self, path, **kwargs):
        return path.read_text(**kwargs)

    def is_file(self, path):
        return path.is_file()

    def stat(self, path):
        return path.stat()

    def resolve(self, path):
        return path.resolve()

    def mkdir(self, path, **kwargs):
        path.mkdir(**kwargs)

    def rglob(self, path, pattern):
        return sorted(path.rglob(pattern))

    def load_events(self, match_id, version=None, run_id=None):
        return load_events_path(self.telemetry_path(match_id, version, run_id))

    def telemetry_path(
        self, match_id: str, version: str | None = None, run_id: str | None = None
    ) -> pathlib.Path:
        bases = []
        if version:
            base = (self.root / "data/bronze") / version
            if run_id:
                base /= run_id
            bases.append(base / "telemetry")
        else:
            bases.extend(
                ((self.root / "data/bronze") / name / "telemetry" for name in ("v1", "v2"))
            )
        for base in bases:
            for suffix in (".json.gz", ".json"):
                candidate = base / f"{match_id}{suffix}"
                if candidate.exists():
                    return candidate
        legacy = (self.root / "data") / f"{match_id}.telemetry.json"
        if legacy.exists():
            return legacy
        raise FileNotFoundError(f"telemetry 없음: {match_id}")

    def link_or_copy(self, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha256_file(source) != sha256_file(target):
                raise RuntimeError(f"이관 대상 내용 불일치: {target.relative_to(self.root)}")
            return
        try:
            os.link(source, target)
        except OSError:
            fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
            os.close(fd)
            try:
                shutil.copy2(source, temporary)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    def read_ledger(self, path):
        if not path.exists():
            return []
        body = path.read_text(encoding="utf-8")
        if body and not body.endswith("\n"):
            raise ValueError("호출 원장 마지막 행이 완성되지 않음")
        rows = [json.loads(line) for line in body.splitlines() if line.strip()]
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("호출 원장 행 형식 오류")
        return rows

    def append_ledger(self, path, row):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
