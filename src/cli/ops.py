"""Run local telemetry batches, inspect results and manage human review."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from src.domain.errors import OpsError
from src.domain.review import REVIEW_STATES
from src.adapters.files import ROOT
from src.adapters.sqlite_ops import connect
from .ops_composition import (
    DEFAULT_STATE,
    operations,
    run_batch,
    retry_job,
    report_batch,
    review_list,
    review_show,
    review_change,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "status", "retry", "report", "demo"):
        child = sub.add_parser(command)
        child.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
        if command != "demo":
            child.add_argument("--batch-id", required=True)
        if command == "run":
            child.add_argument("--manifest", type=Path)
            child.add_argument("--source-root", type=Path, default=ROOT)
        if command == "retry":
            child.add_argument("--job-id", required=True)
        if command == "status":
            child.add_argument("--json", action="store_true")
    review = sub.add_parser("review").add_subparsers(dest="review_command", required=True)
    for command in ("list", "show", "start", "note", "complete", "reopen"):
        child = review.add_parser(command)
        child.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
        if command == "list":
            child.add_argument("--batch-id")
            child.add_argument("--state", choices=REVIEW_STATES)
        else:
            child.add_argument("--case-id", required=True)
        if command not in ("list", "show"):
            child.add_argument("--operator", required=True)
        if command == "note":
            child.add_argument("--note", required=True)
    args = parser.parse_args()
    try:
        if args.command == "review":
            if args.review_command == "list":
                result = review_list(
                    state_dir=args.state_dir, batch_id=args.batch_id, state=args.state
                )
            elif args.review_command == "show":
                result = review_show(args.case_id, state_dir=args.state_dir)
            else:
                result = review_change(
                    args.review_command,
                    args.case_id,
                    args.operator,
                    note=getattr(args, "note", None),
                    state_dir=args.state_dir,
                )
        elif args.command == "run":
            result = run_batch(
                args.batch_id, args.manifest, state_dir=args.state_dir, source_root=args.source_root
            )
        elif args.command == "retry":
            retry_job(args.batch_id, args.job_id, state_dir=args.state_dir)
            result = {"batch_id": args.batch_id, "job_id": args.job_id, "state": "QUEUED"}
        elif args.command == "report":
            result = report_batch(args.batch_id, state_dir=args.state_dir)
        elif args.command == "demo":
            from .demo_composition import demo

            result = demo(args.state_dir)
        else:
            with closing(connect(args.state_dir, readonly=True)) as connection:
                service = operations(connection)
                result = service.status(args.batch_id)
        if args.command == "status" and not args.json:
            print(
                f"{result['batch_id']}: {result['counts']} · events={result['metrics']['events']}"
            )
        else:
            print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0 if result.get("complete", True) else 1
    except (
        RuntimeError,
        ValueError,
        TypeError,
        KeyError,
        OSError,
        sqlite3.Error,
        SystemExit,
    ) as error:
        # 고정 코드와 예외 유형만 출력하고 원문·SQL 인수·인증 정보는 남기지 않는다.
        code = (
            "INPUT_TOKEN"
            if isinstance(error, SystemExit)
            else (str(error) if isinstance(error, OpsError) else type(error).__name__)
        )
        print(json.dumps({"error": code}))
        return 2
