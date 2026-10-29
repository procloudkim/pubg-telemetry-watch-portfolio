"""Audit CLI arguments, diagnostics and output."""

import argparse
import sys
from src.adapters.files import BRONZE, SILVER, MANIFESTS, REPORTS, atomic_write_bytes
from src.domain.tokens import validate_token
from .audit_composition import graph_audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_id = validate_token(args.run_id, "run id")
    bronze = BRONZE / "v3" / run_id
    silver = SILVER / "v3" / run_id
    manifest = MANIFESTS / "v3" / f"{run_id}.json"
    output = REPORTS / "graph-feasibility.md"
    try:
        summary, raw_tokens = graph_audit().analyze_run(run_id, bronze, silver, manifest)
        graph_audit().write_report(summary, raw_tokens, output)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        atomic_write_bytes(
            output, b"# Graph feasibility audit\n\nStatus: `STOP`\n\nInput validation failed.\n"
        )
        print("graph spike: STOP input validation failed", file=sys.stderr)
        return 1
    print(
        f"graph spike: {summary['decision']} matches={summary['source']['selected_matches']} "
        f"players={summary['relationship_query']['players']} "
        f"repeated_pairs={summary['relationship_query']['repeated_at_least_2']}"
    )
    return 0 if summary["decision"] == "FEASIBLE_FOR_NEO4J_REVIEW" else 1
