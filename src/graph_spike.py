"""Compatibility entry point for the graph_spike audit."""

from .cli.graph_spike import main
from .cli.audit_composition import graph_audit, sql_audit
from .adapters.files import ROOT
from .adapters.sqlite_audit import SQL_PATH
from pathlib import Path


def analyze_run(run_id: str, bronze: Path, silver: Path, manifest_path: Path):
    return graph_audit().analyze_run(run_id, bronze, silver, manifest_path)


def write_report(summary, raw_tokens, path: Path):
    return graph_audit().write_report(summary, raw_tokens, path)


if __name__ == "__main__":
    raise SystemExit(main())
