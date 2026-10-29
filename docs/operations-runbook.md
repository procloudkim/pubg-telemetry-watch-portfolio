# Local operations and reproduction

Use Linux or WSL and a fresh state directory on its local filesystem. Dependencies are installed
before the offline gate. New workload inputs are synthetic; existing research is preserved.
The persistent workflow is defined in [DESIGN §12](../DESIGN.md#12-로컬-배치-운영-계약), queries
in the [SQL catalog](sql/README.md), and boundaries in the [architecture](architecture/operations.md).

## Baseline and comparison

```bash
python -m src.ops_demo --output /tmp/watch-baseline --sizes 1000000 10000000 --repeats 3
python -m src.ops_demo --output /tmp/watch-size100k --sizes 1000000 --match-events 100000 --repeats 3
python -m src.ops_demo --output /tmp/watch-size200k --sizes 1000000 --match-events 200000 --repeats 3
# After freezing the baseline source and applying the reviewed implementation:
python -m src.ops_demo --output /tmp/watch-after --sizes 1000000 10000000 --repeats 3 \
  --compare-to /tmp/watch-baseline
```

Keep the baseline source copy and matching runtime alongside its evidence. Workload preparation
is excluded; each case has one warmup plus three measurements with fresh processes and DBs.
`measurements.json` retains individual measurements, environment, commands, input/source hashes,
attempt timing and actual SQL plan. `summary.json` includes median and range. Synthetic result
files use generator actor identities for cross-version comparison, with 1e-9 float tolerances.
Within a version the exact result hashes must agree. Existing output measurements are not overwritten.

The primary throughput is newly committed events divided by run+report wall seconds. Successful
latency is processing start to immediately after result commit; p95 uses nearest rank `ceil(.95*n)`.
Loss of the later timing write leaves NULL and reduces the sample count. E2E ends after the report
process exits and therefore includes report publication. GNU Time `%M` measures each run and report
process through exit; they execute sequentially, so their RSS values must not be added as concurrent
memory. The old per-attempt VmHWM remains a separate partial measurement.

See the [GNU Time memory documentation](https://www.gnu.org/software/time/manual/html_node/Memory-Resources.html)
for the external RSS field. Match-size sensitivity is separate from total input size. This synthetic
profile is not a measurement of actual service capacity or detection accuracy.

## Review workflow

The CLI provides `review list`, `show`, `start`, `note`, `complete` and `reopen`,
all with the same `--state-dir` convention. `list` accepts batch/state filters and the other commands
use case IDs. Mutations require an operator label. `REVIEW` is a signal interpretation; COMPLETED
only ends the human work item. Operator labels are local attribution, not authenticated identities.
Keep free-text notes in the private operational DB and include them explicitly when exporting backups.

```bash
python -m src.ops demo --state-dir /tmp/watch-review
python -m src.ops review list --state-dir /tmp/watch-review --state OPEN
# Use a case_id from list:
python -m src.ops review show --state-dir /tmp/watch-review --case-id CASE_ID
python -m src.ops review start --state-dir /tmp/watch-review --case-id CASE_ID --operator reviewer-1
python -m src.ops review note --state-dir /tmp/watch-review --case-id CASE_ID --operator reviewer-1 --note 'Synthetic evidence inspected.'
python -m src.ops review complete --state-dir /tmp/watch-review --case-id CASE_ID --operator reviewer-1
python -m src.ops review reopen --state-dir /tmp/watch-review --case-id CASE_ID --operator reviewer-1
```

For the complete synthetic demonstration in a new directory, run:

```bash
python tools/operations_walkthrough.py --output /tmp/watch-walkthrough
```

It generates inputs, measures processing/reporting, queries REVIEW evidence, records a note and
completion, exits a worker before commit, resumes it, verifies no duplicate results or lost human
records, then uses SQLite backup and restores/reissues byte-identical completed reports.
`verification.json` records commands, the expected crash exit 37, timing, checksums and counts.

The refactored code can read, review and report an existing schema-v2 database without migrating it.
A different code fingerprint still prevents resuming its batch: preserve the matching old source/runtime
or register a separate experiment. Do not merge case identities across versions. Source hashes now
cover recursive `src/**/*.py` and `sql/**/*.sql`; the benchmark tool has its own generator hash.

Old schemas are preserved with their original code/runtime. New code rejects an incompatible
schema without automatic conversion; use a separate state directory for a new experiment.

## Offline gate

```bash
python -m pip install -e ".[typecheck]"
validation_run=$(mktemp -d /tmp/watch-offline.XXXXXX)
parent_netns=$(readlink /proc/self/ns/net)
sudo unshare --net -- "$(command -v python)" tools/offline_check.py \
  --parent-netns "$parent_netns" --state-dir "$validation_run/demo" \
  --record-dir "$validation_run/checks"
sudo "$(command -v python)" tools/validation_status.py "$validation_run/checks/result.json"
```

The gate verifies a different network namespace, only the loopback interface, unreachable external
route and child namespace inheritance before running configured mypy, tests, demo and SQL coverage. Isolation
failure is an error, not a skipped success. GitHub Actions applies this on Python 3.10 and 3.12
after dependency installation. The [unshare manual](https://man7.org/linux/man-pages/man1/unshare.1.html)
describes namespace isolation. A local pass does not claim a remote CI run.

`checks/result.json` records each step's status, actual command, scope, exit code, duration and
relative log path. Its validation conditions include file hashes for source, tests/fixtures, tools,
configuration and public documents, plus Python, SQLite and installed package versions. It does
not read `.env`, raw `data/` or `reports/`, or dump environment variables. The production runtime
fingerprint is unchanged. CI prints the JSON and step logs into the job log; it does not publish
a separate artifact. Preserve local records outside `/tmp` when they need to survive cleanup.
When the gate runs through `sudo`, read its result with matching privileges: the atomic JSON
writer uses private file permissions on Linux filesystems.

The reader prints JSON with the historical status, step commands/scopes/durations, log locations,
and changed file/environment keys. It compares the stored conditions with the checkout containing
the reader and its current Python environment; use the same interpreter as the gate. It does not
change records, execute stored commands, parse human log text, or infer a test count. CI runs the
reader even after a failed gate, then prints raw evidence in a separate always-run step.

Exit 0 means a coherent schema-1 `PASS`, matching current conditions and readable regular logs.
Exit 1 means a valid record is failed, interrupted, incomplete, missing required logs, or stale.
Exit 2 means invalid/unreadable input or unavailable current conditions; the latter preserves the
historical status. Symlink and non-regular logs are rejected. A `RUNNING` record may still be active:
check the process before starting another gate. Results and hashes are local evidence, not
tamper-proof execution proof or permission to skip a new gate or release a held change.

Only `PASS` with all five steps passed and unchanged before/after conditions is a completed gate.
`FAIL`, `INTERRUPTED`, `RUNNING`, missing results and `NOT_RUN` steps are not success evidence.
SIGINT/SIGTERM stop the active child process group and record interruption. SIGKILL or power loss
can leave an incomplete `RUNNING` record; there is no automatic resume or result reuse. Comparing
before/after hashes does not detect an edit that was reverted during execution. Use an unchanged
checkout while checking. An existing record directory is rejected without overwriting it.

Without `--record-dir`, the original tests/demo/SQL invocation still works and does not add mypy.
The recording regression tests create user/network namespaces themselves; run with the necessary
Linux namespace permissions. Type diagnostics cover the four configured runtime files and the reader.

## Recovery and backup boundaries

On process termination, run the same batch again. An unfinished attempt becomes INTERRUPTED
and a queued job; a committed result is reused. FAILED input jobs require restoring the original
bytes and explicit `retry`. Never silently replace a registered input with different content.
Database errors stop the writer. A busy writer returns WORKER_BUSY before mutation.

Create a consistent snapshot using Python SQLite's `Connection.backup`, then close and check
`PRAGMA integrity_check` and `PRAGMA foreign_key_check`. Include all review/history tables.
Restore the backup into a fresh state directory, compare table contents and result hashes, and
reissue the completed batch report. Copying only the main file of a running WAL database is insufficient.
Completed reports do not require re-reading telemetry, but resuming unfinished jobs requires the
registered input paths and original bytes. Source-path relocation is not an automatic migration.

Process exit tests do not establish resilience to hardware power loss or disk failure. Human CLI
usability and long unattended operation require their own evidence.

## GCP staging status

Staging is blocked pending current credit, exact expiry and account mode. Compute API is currently
disabled. No VM or new cloud resource has been created by this run. Details and account context
remain in the local blocker record. Do not activate the API or create resources until this prerequisite
is resolved; the alternatives below are documentation only.

The proposed host is one Linux `e2-standard-2` VM with SQLite, no public application endpoint and
no game API credentials. Google documents that shape as 2 vCPU and 8 GB in its
[machine specifications](https://docs.cloud.google.com/compute/docs/general-purpose-machines).
Before any resource action, record existing resources, the exact new-resource list, cost estimate,
remaining credit and expiry. A billing-enabled project alone does not prove remaining trial credit.
[Trial expiry or credit exhaustion](https://docs.cloud.google.com/free/docs/free-cloud-features)
can end access. A paid upgrade is outside this run's defaults.

Once unblocked, transfer the exact synthetic input and source/runtime bundle, compare baseline
and feature revisions on the same VM, record repeat and restart recovery, and export a SQLite
backup plus measurements/reports. Complete the first full export and local restore at least
24 hours before expiry. Report only the actual observation duration. Cleanup follows the separate
approved retirement inventory and evidence gates, including existing resources when explicitly
in scope. The current project's later retirement handoff supersedes the initial new-resources-only
plan; see [ADR 020](adr/020-scheduled-cloud-retirement.md) and the private execution contract.
Its inventory, scheduling, retention and deletion-limit blockers remain unresolved. No cleanup or
automatic schedule has been implemented here; check remaining disks, snapshots and storage only
within that approved process.
If time is insufficient, a shorter cloud observation or a later local-only reproduction is possible;
neither alternative has been executed to bypass the current blocker.
