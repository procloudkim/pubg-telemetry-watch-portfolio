"""Read recorded validation evidence without executing its commands."""

import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.offline_check import conditions_hash, validation_conditions

STEP_NAMES = ("namespace", "typecheck", "unittest", "demo", "sql-inventory")


class InvalidRecord(ValueError):
    """A fixed diagnostic; never include arbitrary input text."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise InvalidRecord(code)


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise InvalidRecord("NONFINITE_JSON_NUMBER")


def timestamp(value) -> datetime:
    require(isinstance(value, str), "INVALID_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise InvalidRecord("INVALID_TIMESTAMP") from None
    require(parsed.tzinfo is not None, "INVALID_TIMESTAMP")
    return parsed


def valid_digest(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def check_conditions(value) -> None:
    require(isinstance(value, dict), "INVALID_CONDITIONS")
    files, environment = value.get("files"), value.get("environment")
    require(isinstance(files, dict) and bool(files), "INVALID_CONDITION_FILES")
    require(all(isinstance(name, str) and name and valid_digest(digest)
                for name, digest in files.items()), "INVALID_CONDITION_FILES")
    require(isinstance(environment, dict), "INVALID_ENVIRONMENT")
    require(all(isinstance(environment.get(key), str) and environment[key]
                for key in ("python", "executable", "platform", "sqlite")), "INVALID_ENVIRONMENT")
    require(type(environment.get("optimize")) is int, "INVALID_ENVIRONMENT")
    packages = environment.get("packages")
    require(isinstance(packages, dict) and all(
        isinstance(name, str) and name and isinstance(version, str) and version
        for name, version in packages.items()), "INVALID_PACKAGES")


def read_record(path: Path) -> dict:
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK), "r", encoding="utf-8") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "RECORD_NOT_REGULAR_FILE")
        record = json.load(stream, object_pairs_hook=unique_object, parse_constant=reject_constant)
    require(isinstance(record, dict), "RECORD_MUST_BE_OBJECT")
    require(type(record.get("schema_version")) is int and record["schema_version"] == 1,
            "UNSUPPORTED_SCHEMA")
    require(record.get("status") in ("PASS", "FAIL", "INTERRUPTED", "RUNNING"), "INVALID_STATUS")
    started = timestamp(record.get("started_at"))
    require(isinstance(record.get("cwd"), str) and bool(record["cwd"]), "INVALID_CWD")
    invocation = record.get("invocation")
    require(isinstance(invocation, list) and bool(invocation) and all(
        isinstance(argument, str) and argument for argument in invocation), "INVALID_INVOCATION")
    namespace = record.get("namespace")
    require(isinstance(namespace, dict) and all(isinstance(namespace.get(key), str) and namespace[key]
            for key in ("parent", "current")), "INVALID_NAMESPACE")
    check_conditions(record.get("conditions"))
    require(record.get("conditions_sha256") == conditions_hash(record["conditions"]),
            "CONDITIONS_HASH_MISMATCH")
    steps = record.get("steps")
    require(isinstance(steps, list) and len(steps) == len(STEP_NAMES), "INVALID_STEPS")
    for index, (step, name) in enumerate(zip(steps, STEP_NAMES)):
        require(isinstance(step, dict) and step.get("name") == name, "INVALID_STEP_ORDER")
        require(step.get("status") in ("PASS", "FAIL", "INTERRUPTED", "RUNNING", "NOT_RUN"),
                "INVALID_STEP_STATUS")
        require(isinstance(step.get("scope"), str) and bool(step["scope"]), "INVALID_SCOPE")
        require(step.get("log") == f"{index:02d}-{name}.log", "INVALID_LOG_PATH")
        command = step.get("command")
        require("command" in step and (command is None if name == "namespace" else
                isinstance(command, list) and bool(command) and all(
                    isinstance(argument, str) and argument for argument in command)), "INVALID_COMMAND")
        require("exit_code" in step and (step["exit_code"] is None or type(step["exit_code"]) is int),
                "INVALID_STEP_EXIT_CODE")
        duration = step.get("elapsed_seconds")
        require("elapsed_seconds" in step and (duration is None or
                type(duration) in (int, float) and 0 <= duration < math.inf), "INVALID_DURATION")
        if step["status"] == "PASS":
            require(step["exit_code"] == 0 and duration is not None, "INCONSISTENT_STEP_PASS")
            if name == "namespace":
                require(namespace["parent"] != namespace["current"], "INCONSISTENT_NAMESPACE_PASS")
    if record["status"] != "RUNNING":
        require(timestamp(record.get("finished_at")) >= started, "INVALID_FINISH_TIME")
        require(type(record.get("exit_code")) is int, "INVALID_EXIT_CODE")
        require(type(record.get("conditions_unchanged")) is bool, "INVALID_CONDITIONS_UNCHANGED")
        final = record.get("final_conditions", record["conditions"])
        check_conditions(final)
        require(record.get("final_conditions_sha256") == conditions_hash(final), "FINAL_HASH_MISMATCH")
        require(record["conditions_unchanged"] == (final == record["conditions"]),
                "INCONSISTENT_FINAL_CONDITIONS")
        if record["status"] == "PASS":
            require(record["exit_code"] == 0 and record["conditions_unchanged"] and
                    all(step["status"] == "PASS" for step in steps), "INCONSISTENT_PASS")
        else:
            require(record["exit_code"] != 0, "INCONSISTENT_FAILURE")
    else:
        require("exit_code" in record and record["exit_code"] is None, "INVALID_RUNNING_EXIT_CODE")
    return record


def log_available(path: Path) -> bool:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            return stat.S_ISREG(os.fstat(descriptor).st_mode)
        finally:
            os.close(descriptor)
    except OSError:
        return False


def summarize(path: Path) -> tuple[dict, int]:
    record = read_record(path)
    steps = [{**step, "log": str(path.parent / step["log"]),
              "log_available": log_available(path.parent / step["log"])} for step in record["steps"]]
    issues = [f"LOG_UNAVAILABLE:{step['name']}" for step in steps
              if step["status"] in ("PASS", "FAIL", "INTERRUPTED") and not step["log_available"]]
    try:
        current = validation_conditions()
        check_conditions(current)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        current = None
        issues.append("CURRENT_CONDITIONS_UNAVAILABLE")
    matches = conditions_hash(current) == record["conditions_sha256"] if current is not None else None
    passed = record["status"] == "PASS" and matches is True and not issues
    if current is None:
        action = "Inspect current files and the Python/package environment, then read this record again."
    elif record["status"] == "RUNNING":
        action = "Check whether the recorded process is still running before starting a new gate."
    elif issues:
        action = "Restore the missing evidence or run the full gate in a new directory."
    elif record["status"] == "INTERRUPTED":
        action = "Inspect the interrupted step and run the full gate in a new directory."
    elif any(step["status"] == "FAIL" for step in steps):
        failed = ", ".join(step["name"] for step in steps if step["status"] == "FAIL")
        action = f"Inspect {failed} and its log, then run the full gate in a new directory."
    elif passed:
        action = "Review the local evidence; existing release holds still apply."
    else:
        action = "Run the full gate for current conditions in a new directory."
    summary = {
        "record": str(path),
        "recorded_status": record["status"],
        "started_at": record["started_at"],
        "finished_at": record.get("finished_at"),
        "record_valid": True,
        "conditions_match": matches,
        "current_pass": passed,
        "differences": None if current is None else {
            group: sorted(key for key in record["conditions"][group].keys() | current[group].keys()
                          if record["conditions"][group].get(key) != current[group].get(key))
            for group in ("files", "environment")
        },
        "steps": steps,
        "issues": issues,
        "next_action": action,
    }
    return summary, 2 if current is None else 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    path = args.result
    try:
        path = path.resolve()
        summary, exit_code = summarize(path)
    except (OSError, ValueError, RuntimeError) as error:
        code = str(error) if isinstance(error, InvalidRecord) else type(error).__name__
        summary = {"record": str(path), "recorded_status": None, "record_valid": False,
                   "conditions_match": None, "current_pass": False, "steps": [],
                   "issues": [code], "next_action": "Check the result file and its schema; no checks were run."}
        exit_code = 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
