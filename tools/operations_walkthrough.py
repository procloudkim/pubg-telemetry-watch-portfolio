"""Synthetic CLI walkthrough: review, process exit, replay, SQLite backup and restore."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import ops
from src.common import sha256_file
from src.ops_demo import r2_fixture, timed_cli, write_inputs
from src.v3 import stable_json


def walkthrough(output):
    if not __debug__:
        raise RuntimeError("WALKTHROUGH_REQUIRES_ASSERTIONS")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    state, restored = output / "state", output / "restored"
    inputs = output / "inputs"
    fixture = json.loads(
        (ROOT / "tests/fixtures/TESTMATCH.telemetry.json").read_text(encoding="utf-8")
    )
    manifest = write_inputs(inputs, [("TESTMATCH", fixture), ("R2MATCH", r2_fixture())])
    commands = []

    def cli(*arguments):
        command = [sys.executable, "-m", "src.ops", *arguments, "--state-dir", str(state)]
        child = subprocess.run(command, capture_output=True, text=True, check=True)
        commands.append({"command": command, "exit_code": child.returncode})
        return json.loads(child.stdout)

    started = time.perf_counter()
    result, run_s, run_rss, command = timed_cli(
        [
            "run",
            "--batch-id",
            "walkthrough",
            "--manifest",
            str(manifest),
            "--source-root",
            str(inputs),
            "--state-dir",
            str(state),
        ],
        output,
        "run",
    )
    commands.append({"command": command, "exit_code": 0})
    _, report_s, report_rss, command = timed_cli(
        ["report", "--batch-id", "walkthrough", "--state-dir", str(state)], output, "report"
    )
    e2e = time.perf_counter() - started
    commands.append({"command": command, "exit_code": 0})
    cases = cli("review", "list", "--batch-id", "walkthrough")["cases"]
    assert len(cases) == 3 and result["complete"]
    case = cases[0]["case_id"]
    evidence = cli("review", "show", "--case-id", case)
    assert evidence["signal"]["evidence"]
    for action in ("start", "note", "complete"):
        cli(
            "review",
            action,
            "--case-id",
            case,
            "--operator",
            "synthetic-reviewer",
            *(
                ["--note", "Synthetic evidence inspected; workflow demonstration only."]
                if action == "note"
                else []
            ),
        )
    before = cli("review", "show", "--case-id", case)
    # The crash injector exists only in this synthetic walkthrough, never as a worker CLI flag.
    crash_inputs = output / "crash-inputs"
    crash_manifest = write_inputs(crash_inputs, [("CRASHMATCH", fixture)])
    with ops.writer_lock(state), closing(ops.connect(state)) as connection:
        ops.register(connection, "crash", crash_manifest, crash_inputs)
    script = """
import os,sqlite3,sys
from pathlib import Path
from unittest.mock import patch
from src import ops
from src.adapters import sqlite_ops
class Connection(sqlite3.Connection):
    def commit(self):
        os._exit(37)
original=sqlite3.connect
with patch.object(sqlite_ops.sqlite3,'connect',side_effect=lambda *a,**k: original(*a,**k,factory=Connection)):
    ops.run_batch('crash',state_dir=Path(sys.argv[1]))
"""
    crash_command = [sys.executable, "-c", script, str(state)]
    child = subprocess.run(crash_command, capture_output=True, text=True)
    assert child.returncode == 37, child.stderr
    commands.append(
        {
            "command": ["python", "synthetic before-commit crash injector", str(state)],
            "exit_code": 37,
        }
    )
    tick = time.perf_counter()
    recovered = cli("run", "--batch-id", "crash")
    recovery_s = time.perf_counter() - tick
    assert recovered["complete"] and [a["outcome"] for a in recovered["attempts"]] == [
        "INTERRUPTED",
        "SUCCEEDED",
    ]
    repeated = cli(
        "run",
        "--batch-id",
        "walkthrough",
        "--manifest",
        str(manifest),
        "--source-root",
        str(inputs),
    )
    assert repeated["attempts"] == result["attempts"]
    cli("report", "--batch-id", "walkthrough")
    assert cli("review", "show", "--case-id", case) == before
    assert len(cli("review", "list")["cases"]) == 5
    restored.mkdir()
    with ops.writer_lock(state), closing(ops.connect(state, readonly=True)) as source:
        with closing(sqlite3.connect(restored / "ops.sqlite3")) as target:
            source.backup(target)
            assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert target.execute("PRAGMA foreign_key_check").fetchall() == []
            assert list(source.iterdump()) == list(target.iterdump())
            counts = {
                table: target.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                for table in ("job", "attempt", "review_signal", "review_case", "review_history")
            }
    backup_hash = sha256_file(restored / "ops.sqlite3")
    ops.report_batch("walkthrough", state_dir=restored)
    assert ops.review_show(case, state_dir=restored) == before
    for path in (state / "reports/walkthrough").iterdir():
        assert path.read_bytes() == (restored / "reports/walkthrough" / path.name).read_bytes()
    record = {
        "status": "PASS",
        "code_sha256": ops.fingerprint(),
        "runtime": ops.runtime(),
        "input_sha256": sha256_file(manifest),
        "metrics": result["metrics"],
        "run_seconds": run_s,
        "report_seconds": report_s,
        "e2e_seconds": e2e,
        "events_per_second": result["metrics"]["events"] / (run_s + report_s),
        "run_peak_rss_kib": run_rss,
        "report_peak_rss_kib": report_rss,
        "recovery_seconds": recovery_s,
        "backup_sha256": backup_hash,
        "counts": counts,
        "commands": commands,
        "review_history_preserved": True,
        "restored_report_bytes_equal": True,
        "limitations": [
            "synthetic workflow, not independent human review",
            "process exit, not hardware failure",
        ],
    }
    (output / "verification.json").write_bytes(stable_json(record))
    print(json.dumps(record, ensure_ascii=False))
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    walkthrough(parser.parse_args().output)
