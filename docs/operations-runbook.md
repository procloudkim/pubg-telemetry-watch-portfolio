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

The 2026-10-30 run reproduced public source commit
[`324c376`](https://github.com/procloudkim/pubg-telemetry-watch-portfolio/commit/324c37659d3b7ee6d0ce1e29fc499543e0a8af3b)
on one Seoul `e2-standard-2` VM: 2 vCPU, 8 GB RAM, Ubuntu 24.04.5, a 30 GB balanced
persistent disk, Python 3.10.20 and SQLite 3.50.4. Access used IAP; the VM had no external IP,
service account or game API credentials. The workload used synthetic inputs only.

| Evidence | Observed result |
|---|---|
| Public delivery | Source-only repository; [CI run 40975020519](https://github.com/procloudkim/pubg-telemetry-watch-portfolio/actions/runs/40975020519) passed on Python 3.10 and 3.12 for the linked commit |
| Fresh public clone | Fresh Python 3.10 environment, original workspace hidden, network isolated: configured type check, 92 tests, TESTMATCH, demo, SQL inventory and result reader passed |
| Cloud offline gate | The same checks passed on the VM; type checking covers the configured five files, not the whole repository |
| Actual walkthrough | Before-commit process exit 37, resume to SUCCEEDED, no duplicate result, review history preserved; 3 jobs, 4 attempts, 5 cases and 8 history rows |
| Recording | OBS captured the actual terminal walkthrough: 106.766 seconds, 1280×800 at 30 fps; no microphone/desktop audio sources. Full video playback review was not performed |
| Independent restore | Private Drive download: source/runtime/wheel bundle (5,432 file hashes), walkthrough bundle (73 file hashes); SQLite integrity/FK, full contents, history and regenerated report bytes matched |
| Existing project data | Private Drive archive reassembled and 85 files verified; a managed Firestore import into a separate temporary database matched all 53 original document paths and field hashes. Container descriptor/blob integrity was checked; application redeployment was not tested |
| Benchmark archive | 624 files, including exact inputs, measurements, query plans and logs, verified after private Drive download and reassembly |
| VM and restore-test cleanup | Benchmark VM is TERMINATED with disk retained; temporary Firestore database deletion completed and its active name returned 404. Original database remains |
| External runner rehearsal | Windows Task Scheduler fired a one-time read-only check at the registered time; existing authentication, project identity and backup hashes passed. This was not a shutdown task |
| Retirement | Whole-project cleanup, billing unlink and shutdown remain unexecuted; automatic deletion is not scheduled |

Two initial cloud isolation attempts failed because of home-directory traversal and user-namespace
restrictions. Extracting the same frozen source under `/opt` allowed the complete gate to pass;
system security settings were not changed. Those failures remain in the private evidence.
The first Firestore hash comparison used different Unicode JSON escaping; direct field equality
and a repeat using the original canonical encoding verified all documents. These were verification
setup corrections, not product-code changes.

### Cloud benchmark observation

Baseline is the archived 2026-10-27 source (`7dbb3688…`); current runtime source fingerprint is
`e6b68274…`. Each version ran four input profiles, with one warmup and three measured repetitions:
32 executions in total, including 8 warmups. All runs used fresh processes and databases on the
same VM, sequentially, from 01:51:17 to 02:40:27 UTC on 2026-10-30. Input manifest hashes and
runtime versions matched; canonical rule/count/evidence comparisons passed in every current run.
The historical baseline source and complete raw evidence remain in the private backup; the public
clone can reproduce the current harness with the commands above.

The table excludes warmups. Time is run plus report through process exit, excluding input
generation and comparison; RSS is each run process's GNU Time peak in KiB, not combined with
report RSS. Brackets show the three measured repetitions' minimum and maximum.

| Events / maximum match | Version | run+report seconds, median [range] | events/s, median | run RSS KiB, median [range] |
|---|---|---:|---:|---:|
| 1M / 40k | baseline | 26.496 [25.914–27.103] | 37,741 | 88,148 [84,932–94,096] |
| 10M / 40k | baseline | 253.176 [252.190–256.552] | 39,498 | 88,644 [88,620–88,788] |
| 1M / 100k | baseline | 26.942 [26.914–27.357] | 37,117 | 171,972 [171,788–172,084] |
| 1M / 200k | baseline | 28.242 [28.045–28.317] | 35,409 | 310,420 [310,400–310,548] |
| 1M / 40k | current | 25.837 [25.788–26.121] | 38,704 | 80,448 [80,128–80,504] |
| 10M / 40k | current | 250.776 [250.733–261.876] | 39,876 | 80,876 [80,852–81,772] |
| 1M / 100k | current | 26.937 [26.314–27.249] | 37,124 | 164,096 [163,824–164,100] |
| 1M / 200k | current | 28.569 [28.283–28.666] | 35,003 | 302,552 [272,684–302,620] |

These are synthetic observations on one VM. Version order was fixed, OS caches were not reset,
and host scheduling was not controlled. Small timing differences do not establish an optimization
benefit. Memory grows with maximum match size; 1M versus 10M at 40k per match does not prove
unbounded memory independence. This run does not establish real-service capacity, independent
human usability, hardware-failure recovery or 72-hour unattended operation.

The benchmark archive SHA-256 is
`9b13a2b4a4c4628cc8afe7eba75b833ebb4f305f2b631f203cd35b2648420c64`.
The walkthrough backup SHA-256 is
`c5ec729f51f41ddddc2d564bd57025af7d2173cebd428282796ded175108e308`.
Private raw evidence includes individual warmup/measured results and the original recording;
these archives are not part of the public clone.

### Retirement boundary

The user-approved deadline is November 1, 2026, 23:00 KST, with stop/final-sync at 18:00 and
cleanup planned from 20:00. This is not a verified provider trial-expiry timestamp. Trial credit use
was approved; a paid upgrade is outside scope. [Trial expiry or credit exhaustion](https://docs.cloud.google.com/free/docs/free-cloud-features)
can end access independently of that deadline.

Resource discovery and backups progressed, but some Cloud Run/Vertex regional reads returned
provider location-policy errors. Those responses are not empty inventories. The current process
therefore has no armed destructive schedule. Unattended final Drive synchronization and billing
contract checks also need verified evidence. The separate private execution contract and
[ADR 020](adr/020-scheduled-cloud-retirement.md) control project-wide cleanup; this runbook does
not authorize bypassing those gates.

Project shutdown and [provider recovery periods](https://docs.cloud.google.com/resource-manager/docs/delete-restore-projects),
[Storage soft delete](https://docs.cloud.google.com/storage/docs/soft-delete), delayed charges and
permanent deletion are distinct states. Neither stopping a VM nor creating a schedule proves
project cleanup or a zero bill.
