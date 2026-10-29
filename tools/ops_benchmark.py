"""Fixed-environment process benchmark harness; performance is not a shared-CI threshold."""

from contextlib import closing
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from src.adapters.files import ROOT, atomic_write_bytes, sha256_file, write_once
from src.adapters.environment import fingerprint, runtime
from src.adapters.provenance import source_hashes
from src.adapters.sqlite_ops import connect
from src.adapters.sqlite_benchmark import query_plan, synthetic_results
from src.adapters.synthetic import write_inputs
from src.domain.serialization import stable_json
from src.domain.synthetic import load_matches, compare_results


def timed_cli(arguments, directory, label):
    """GNU Time measures each child through exit, including report publication."""
    memory = directory / (label + "-rss.txt")
    command = [
        "/usr/bin/time",
        "-f",
        "%M",
        "-o",
        str(memory),
        sys.executable,
        "-m",
        "src.ops",
        *arguments,
    ]
    started = time.perf_counter()
    child = subprocess.run(command, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    if child.returncode:
        raise RuntimeError(f"BENCHMARK_{label.upper()}_FAILED exit={child.returncode}")
    return json.loads(child.stdout), elapsed, int(memory.read_text().strip()), command


def benchmark(
    destination,
    *,
    sizes=(1000000, 10000000),
    repeats=3,
    real_manifests=(),
    match_events=40000,
    compare_to=None,
):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / "measurements.json").exists():
        raise RuntimeError("BENCHMARK_OUTPUT_EXISTS")
    code_hash = fingerprint()
    sources = source_hashes(ROOT)
    environment = {
        "cpu": next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            "unknown",
        ),
        "logical_cpus": os.cpu_count(),
        "affinity": sorted(os.sched_getaffinity(0)),
        "memory_total": Path("/proc/meminfo").read_text().splitlines()[0],
        "gnu_time": subprocess.check_output(["/usr/bin/time", "--version"], text=True).splitlines()[
            0
        ],
        "command": [sys.executable, "-m", "src.ops_demo", *sys.argv[1:]],
    }
    cases = []
    for size in sizes:
        root = destination / f"input-{size}"
        manifest = write_inputs(
            root, load_matches(size, match_events=match_events), compressed=True
        )
        cases.append((f"synthetic-{size}", manifest, root))
    cases += [("real-" + Path(path).stem, Path(path).resolve(), ROOT) for path in real_manifests]
    measurements = []
    for label, manifest, root in cases:
        for iteration in range(repeats + 1):
            with tempfile.TemporaryDirectory(prefix="ops-bench-", dir=destination) as temporary:
                if fingerprint() != code_hash:
                    raise RuntimeError("BENCHMARK_SOURCE_CHANGED")
                started = time.perf_counter()
                result, elapsed, run_rss, run_command = timed_cli(
                    [
                        "run",
                        "--batch-id",
                        "benchmark",
                        "--manifest",
                        str(manifest),
                        "--source-root",
                        str(root),
                        "--state-dir",
                        temporary,
                    ],
                    Path(temporary),
                    "run",
                )
                _, report_elapsed, report_rss, report_command = timed_cli(
                    ["report", "--batch-id", "benchmark", "--state-dir", temporary],
                    Path(temporary),
                    "report",
                )
                e2e = time.perf_counter() - started
                if fingerprint() != code_hash or result["code_sha256"] != code_hash:
                    raise RuntimeError("BENCHMARK_SOURCE_CHANGED")
                db_bytes = sum(p.stat().st_size for p in Path(temporary).glob("ops.sqlite3*"))
                with closing(connect(Path(temporary))) as connection:
                    plan = query_plan(connection, result)
                    if label.startswith("synthetic-"):
                        canonical = synthetic_results(connection)
                        path = destination / (label + "-results.json")
                        write_once(path, stable_json(canonical))
                        if compare_to is not None:
                            previous = json.loads((Path(compare_to) / path.name).read_text(encoding="utf-8"))
                            if not compare_results(previous, canonical):
                                raise RuntimeError("BASELINE_RESULT_MISMATCH")
                successful = [a for a in result["attempts"] if a["outcome"] == "SUCCEEDED"]
                if len(successful) != result["counts"]["SUCCEEDED"] or result["metrics"]["retries"]:
                    raise RuntimeError("BENCHMARK_NOT_FRESH_SUCCESS")
                row = {
                    "query_plan": plan,
                    "rule_protocol": result["rule_protocol"],
                    "case": label,
                    "iteration": iteration,
                    "warmup": iteration == 0,
                    "wall_seconds": elapsed,
                    "report_seconds": report_elapsed,
                    "total_seconds": elapsed + report_elapsed,
                    "e2e_seconds": e2e,
                    "run_peak_rss_kib": run_rss,
                    "report_peak_rss_kib": report_rss,
                    "new_success_events": result["metrics"]["events"],
                    "reused_jobs": 0,
                    "events_per_second": result["metrics"]["events"] / (elapsed + report_elapsed),
                    "db_bytes": db_bytes,
                    "commands": [run_command, report_command],
                    "exit_codes": [0, 0],
                    "attempts": result["attempts"],
                    "filesystems": {
                        "inputs": subprocess.check_output(
                            ["stat", "-f", "-c", "%T", str(root)], text=True
                        ).strip(),
                        "state": subprocess.check_output(
                            ["stat", "-f", "-c", "%T", str(destination)], text=True
                        ).strip(),
                    },
                    "manifest_sha256": sha256_file(manifest),
                    "metrics": result["metrics"],
                    "result_hashes": [job["result_sha256"] for job in result["jobs"]],
                }
                measurements.append(row)
                print(
                    json.dumps(
                        {
                            "case": label,
                            "iteration": iteration,
                            "wall_seconds": round(elapsed, 3),
                            "run_peak_rss_kib": run_rss,
                            "report_peak_rss_kib": report_rss,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                atomic_write_bytes(
                    destination / "measurements.json",
                    stable_json(
                        {
                            "runtime": runtime(),
                            "environment": environment,
                            "source_hashes": sources,
                            "memory_source": "GNU Time %M per run/report process through exit (KiB); metrics.process_peak_rss_kib is pre-commit VmHWM",
                            "latency_source": "processing start through successful commit; post-commit loss remains NULL; p95 nearest rank ceil(.95*n)",
                            "code_sha256": code_hash,
                            "generator_sha256": sha256_file(Path(__file__)),
                            "seed": 20260909,
                            "match_events": match_events,
                            "input_profile": "60% position / 20% attack / 20% damage; 100 synthetic players per match",
                            "measurements": measurements,
                        }
                    ),
                )
    for label, _, _ in cases:
        hashes = [row["result_hashes"] for row in measurements if row["case"] == label]
        if any(value != hashes[0] for value in hashes):
            raise RuntimeError("NONDETERMINISTIC_BENCHMARK_RESULTS")
    fields = (
        "total_seconds",
        "events_per_second",
        "run_peak_rss_kib",
        "report_peak_rss_kib",
        "e2e_seconds",
    )
    summary = {
        label: {
            field: {"median": statistics.median(values), "min": min(values), "max": max(values)}
            for field in fields
            for values in [
                [r[field] for r in measurements if r["case"] == label and not r["warmup"]]
            ]
        }
        for label, _, _ in cases
    }
    atomic_write_bytes(destination / "summary.json", stable_json(summary))
    return measurements
