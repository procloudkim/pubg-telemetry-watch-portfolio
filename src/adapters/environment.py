"""Process provenance and memory measurement."""

from pathlib import Path
import platform
import sqlite3
import uuid
from .files import ROOT
from .provenance import fingerprint as tree_fingerprint
from src.domain.errors import OpsError


def runtime():
    return {
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "platform": platform.platform(),
    }


def peak_rss_kib():
    # ru_maxrss에는 exec 이전의 부모 high-water가 남을 수 있다. Worker의 /proc 값을 사용한다.
    for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1])
    raise OpsError("WORKER_MEMORY_UNAVAILABLE")


def fingerprint():
    return tree_fingerprint(ROOT)


class Environment:
    runtime = staticmethod(runtime)
    peak_rss_kib = staticmethod(peak_rss_kib)
    fingerprint = staticmethod(fingerprint)

    def request_id(self):
        return uuid.uuid4().hex
