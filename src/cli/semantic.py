"""Semantic command diagnostics and output codes."""

import argparse
import json
import sys
from src.adapters.files import ROOT
from src.domain.errors import SemanticConformanceError
from .semantic_composition import semantic_audit


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        manifest = semantic_audit().build_sidecar(args.run_id, root=ROOT)
    except SemanticConformanceError as error:
        print(f"semantic FAIL: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"semantic ERROR: {error}", file=sys.stderr)
        return 2
    graph = next(row for row in manifest["artifacts"] if row["dataset"] == "semantic_graph")
    print(f"semantic: SHADOW_VALIDATED triples={graph['records']} DQ=PASS")
    return 0
