"""Compatibility entry point for the optional semantic sidecar."""

from pathlib import Path
from .domain.errors import SemanticConformanceError
from .domain.semantic import ONTOLOGY_VERSION, PROJECTOR_VERSION, ONTOLOGY_IRI
from .adapters.files import ROOT
from .adapters.rdf import _canonical_ntriples
from .cli.semantic import main
from .cli.semantic_composition import semantic_audit


def build_sidecar(run_id: str, *, root: Path = ROOT) -> dict:
    return semantic_audit().build_sidecar(run_id, root=root)


if __name__ == "__main__":
    raise SystemExit(main())
