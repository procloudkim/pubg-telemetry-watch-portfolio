"""Logical paths supplied by the composition root; constructing them performs no I/O."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def data(self):
        return self.root / "data"

    @property
    def reports(self):
        return self.root / "reports"

    @property
    def bronze(self):
        return self.data / "bronze"

    @property
    def silver(self):
        return self.data / "silver"

    @property
    def gold(self):
        return self.data / "gold"

    @property
    def manifests(self):
        return self.data / "manifests"
