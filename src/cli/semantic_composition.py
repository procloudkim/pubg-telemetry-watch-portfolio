"""Compose semantic validation from read use cases and the local RDF engine."""

from src.adapters.files import LocalFiles
from src.adapters.rdf import RdfEngine
from src.application.semantic import SemanticAudit
from .audit_composition import graph_audit, sql_audit


def semantic_audit():
    return SemanticAudit(LocalFiles(), RdfEngine(), graph_audit(), sql_audit())
