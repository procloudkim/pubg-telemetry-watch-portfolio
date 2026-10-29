"""Fail closed unless tests and all their children run in a separate network namespace."""

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import errno
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import signal
import socket
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.adapters.files import atomic_write_json, sha256_file


def verify_namespace(parent):
    namespace = os.readlink("/proc/self/ns/net")
    # sysfs can retain the mounting namespace's interface view; query the current socket namespace.
    if namespace == parent or {name for _, name in socket.if_nameindex()} != {"lo"}:
        raise RuntimeError("NETWORK_NAMESPACE_NOT_ISOLATED")
    with socket.socket() as connection:
        connection.settimeout(1)
        try:
            connection.connect(("192.0.2.1", 443))
        except OSError as error:
            if error.errno not in (errno.ENETUNREACH, errno.EHOSTUNREACH):
                raise RuntimeError("NETWORK_ISOLATION_NOT_PROVEN") from None
        else:
            raise RuntimeError("NETWORK_REACHABLE")
    child = subprocess.check_output(
        [sys.executable, "-c", "import os; print(os.readlink('/proc/self/ns/net'))"], text=True
    ).strip()
    if child != namespace:
        raise RuntimeError("CHILD_NAMESPACE_MISMATCH")
    print("NETWORK_NAMESPACE_VERIFIED " + namespace, flush=True)


def validation_conditions():
    patterns = (
        "src/**/*.py", "tests/**/*.py", "tests/fixtures/**/*", "tools/**/*.py",
        "sql/**/*.sql", "docs/**/*", ".github/workflows/*", "*.py", "*.toml",
        "README.md", "PLANNING.md", "DESIGN.md", "AGENTS.md", "GLOSSARY.md",
    )
    paths = {path for pattern in patterns for path in ROOT.glob(pattern) if path.is_file()}
    return {
        "files": {str(path.relative_to(ROOT)): sha256_file(path) for path in sorted(paths)},
        "environment": {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "sqlite": sqlite3.sqlite_version,
            "optimize": sys.flags.optimize,
            "packages": dict(sorted(
                (dist.metadata["Name"], dist.version) for dist in metadata.distributions()
            )),
        },
    }


def conditions_hash(conditions):
    return hashlib.sha256(json.dumps(conditions, sort_keys=True).encode()).hexdigest()


def recorded_checks(record_dir, parent_netns, commands):
    record_dir.mkdir(parents=True, exist_ok=False)
    conditions = validation_conditions()
    steps = [{"name": "namespace", "command": None,
              "scope": "verify_namespace: different namespace, loopback, route, child inheritance"}, *commands]
    for index, step in enumerate(steps):
        step.update(status="NOT_RUN", exit_code=None, elapsed_seconds=None,
                    log=f"{index:02d}-{step['name']}.log")
    result = {
        "schema_version": 1,
        "status": "RUNNING",
        "exit_code": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "cwd": str(ROOT),
        "invocation": sys.orig_argv,
        "conditions": conditions,
        "conditions_sha256": conditions_hash(conditions),
        "namespace": {"parent": parent_netns, "current": os.readlink("/proc/self/ns/net")},
        "steps": steps,
    }
    output = record_dir / "result.json"
    atomic_write_json(output, result, indent=2)
    exit_code = 0
    try:
        for step in steps:
            step["status"] = "RUNNING"
            atomic_write_json(output, result, indent=2)
            started = time.perf_counter()
            process = None
            try:
                with (record_dir / step["log"]).open("x", encoding="utf-8") as log:
                    log.write(json.dumps({"command": step["command"], "scope": step["scope"]}) + "\n")
                    log.flush()
                    if step["name"] == "namespace":
                        with redirect_stdout(log), redirect_stderr(log):
                            verify_namespace(parent_netns)
                        step["exit_code"] = 0
                    else:
                        process = subprocess.Popen(
                            step["command"], cwd=ROOT, stdin=subprocess.DEVNULL,
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                        )
                        try:
                            step["exit_code"] = process.wait()
                        except BaseException:
                            # A cancelled test can have children of its own.
                            try:
                                os.killpg(process.pid, signal.SIGTERM)
                            except ProcessLookupError:
                                pass
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                pass
                            finally:
                                try:
                                    os.killpg(process.pid, signal.SIGKILL)
                                except ProcessLookupError:
                                    pass
                            process.wait()
                            raise
                    step["status"] = "PASS" if step["exit_code"] == 0 else "FAIL"
            except (KeyboardInterrupt, SystemExit):
                step["status"] = "INTERRUPTED"
                step["exit_code"] = process.returncode if process else None
                raise
            except Exception as error:
                step["status"] = "FAIL"
                step["error"] = str(error)
                with (record_dir / step["log"]).open("a", encoding="utf-8") as log:
                    log.write(f"{type(error).__name__}: {error}\n")
                raise
            finally:
                step["elapsed_seconds"] = round(time.perf_counter() - started, 6)
                atomic_write_json(output, result, indent=2)
                print(f"{step['name']}: {step['status']} ({record_dir / step['log']})", flush=True)
            if step["status"] != "PASS":
                exit_code = 1
                break
        result["status"] = "PASS" if exit_code == 0 else "FAIL"
    except (KeyboardInterrupt, SystemExit) as error:
        result["status"] = "INTERRUPTED"
        exit_code = error.code if isinstance(error, SystemExit) else 130
    except Exception as error:
        result["status"] = "FAIL"
        result["error"] = str(error)
        exit_code = 1
    finally:
        # shortcut: end-point hashes miss edits reverted mid-run; use a frozen checkout for that guarantee.
        final_conditions = validation_conditions()
        result["final_conditions_sha256"] = conditions_hash(final_conditions)
        result["conditions_unchanged"] = conditions == final_conditions
        if not result["conditions_unchanged"]:
            result["final_conditions"] = final_conditions
            if result["status"] == "PASS":
                result["status"] = "FAIL"
                exit_code = 1
        result["exit_code"] = exit_code
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write_json(output, result, indent=2)
    print(f"{result['status']}: {output}", flush=True)
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-netns", required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--record-dir", type=Path,
                        help="new directory for mypy/offline results and logs (never overwritten)")
    args = parser.parse_args()
    commands = [
        {"name": "unittest", "scope": "unittest discovery: tests",
         "command": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]},
        {"name": "demo", "scope": "synthetic src.ops demo",
         "command": [sys.executable, "-m", "src.ops", "demo", "--state-dir", str(args.state_dir.resolve())]},
        {"name": "sql-inventory", "scope": "SQL inventory and document ownership",
         "command": [sys.executable, "tools/sql_inventory.py", "--check"]},
    ]
    if args.record_dir is None:
        verify_namespace(args.parent_netns)
        for step in commands:
            subprocess.run(step["command"], check=True)
        return 0

    commands.insert(0, {
        "name": "typecheck", "scope": "pyproject.toml [tool.mypy] configured files and options",
        "command": [sys.executable, "-m", "mypy", "--config-file", "pyproject.toml"],
    })

    def interrupt(signum, frame):
        raise SystemExit(128 + signum)

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        return recorded_checks(args.record_dir.resolve(), args.parent_netns, commands)
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    sys.exit(main())
