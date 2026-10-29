"""Audit CLI arguments, diagnostics and output."""

import argparse
from src.adapters.files import ROOT
from src.adapters.sqlite_audit import SQL_PATH
from .audit_composition import sql_audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    summary = sql_audit().audit_run(args.run_id, root=ROOT, sql_path=SQL_PATH)
    funnel = summary["funnel"]
    print(
        f"SQL audit: PASS observations={funnel['accepted_observations']} "
        f"evaluated={funnel['evaluated']} primary={summary['primary']['evaluated_players']} "
        f"candidates={funnel['review_candidates']}"
    )
