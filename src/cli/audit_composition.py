"""Compose read-only audit engines and output adapters."""

from src.adapters.files import LocalFiles
from src.adapters.sqlite_audit import SQLiteAudit
from src.adapters import audit_presentation, graph_presentation
from src.application.sql_audit import SqlAudit
from src.application.graph_audit import GraphAudit


def sql_audit():
    return SqlAudit(LocalFiles(), SQLiteAudit(), audit_presentation._render)


def graph_audit():
    return GraphAudit(LocalFiles(), graph_presentation._render)
