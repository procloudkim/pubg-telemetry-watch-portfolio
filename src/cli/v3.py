"""Fixed cohort collection and evaluation commands."""

import argparse
from src.domain.errors import BudgetExhausted
from .research_composition import research


def main():
    service = research()
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "collect"):
        command = commands.add_parser(name)
        command.add_argument("--run-id", required=True)
        command.add_argument("--session-id", required=True)
        command.add_argument("--api-call-limit", required=True, type=int)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--run-id", required=True)
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.command == "init":
        try:
            service.init_run(args.run_id, args.session_id, args.api_call_limit)
        except BudgetExhausted as error:
            print(error)
    elif args.command == "collect":
        service.collect_run(args.run_id, args.session_id, args.api_call_limit)
    elif args.command == "evaluate":
        service.evaluate_run(args.run_id)
    else:
        service.preflight_run(args.run_id)
