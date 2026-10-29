"""Compatibility entry point for the sql_audit audit."""

from .cli.sql_audit import main
from .cli.audit_composition import graph_audit, sql_audit
from .adapters.files import ROOT
from .adapters.sqlite_audit import SQL_PATH
from pathlib import Path


def audit_run(run_id, *, root=ROOT, sql_path=SQL_PATH, report_path=None):
    return sql_audit().audit_run(run_id, root=root, sql_path=sql_path, report_path=report_path)


if __name__ == "__main__":
    raise SystemExit(main())
