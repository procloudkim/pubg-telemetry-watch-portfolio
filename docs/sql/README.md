# SQL contracts and coverage

## Ownership tree

```text
docs/sql/
├── README.md                 # scope, counting units, dynamic SQL rules
├── owners.json               # exclusive contract → document ownership
├── contracts.json            # statement semantics, transactions, indexes, tests
├── inventory.json / .md      # generated source expressions and two-way links
├── operations/
│   ├── batch.md              # schema, registration, processing, reporting
│   └── review.md             # human review reads and changes
├── research/audit.md         # frozen research, in-memory audit
└── verification/checks.md    # benchmark, backup, tests and examples
```

The [batch](operations/batch.md), [review](operations/review.md), [audit](research/audit.md)
and [verification](verification/checks.md) documents partition all contracts exactly once in
[owners.json](owners.json). `--check` rejects missing or duplicate ownership, unknown source
contracts, incomplete semantics and missing owner documents. Generated inventories and contract
definitions are shared indexes, not a second owner of the queries. Nested SQL documentation is
excluded from source scanning to prevent counting its own generated copies.

## Source coverage and semantics

[Inventory](inventory.md) links every detected execution call, helper call, SQL literal, SQL script
statement and public SQL example to its source. [Machine-readable entries](inventory.json) preserve
the expression, bound parameters and content SHA. Each entry names a [contract](contracts.json)
with purpose, grain/keys, NULL and duplicate semantics, transaction, indexes and verification.
The contract is shared by related statements; it is not a claim that every call is a distinct query.

Run `python tools/sql_inventory.py --check` to check both directions against current source.
After a reviewed query change, run without `--check` and inspect the diff. The scanner uses Python
AST with module and nested `Class.method` ownership, including embedded fault-injection scripts, `sqlite3.complete_statement` for SQL files and SQL
fences for public examples. It does not execute SQL or read operational data. New wrappers and
runtime-generated identifiers require manual review as well as the generated comparison.
SPARQL is a separate language: the six files under `docs/ontology/queries/` are outside this inventory.

| Dynamic source | Finite expansion and binding | Verification |
|---|---|---|
| `adapters.sqlite_ops.connect` executescript | `sql/ops.sql` before `-- @compute`; only an empty DB is initialized | schema mismatch and unknown DB rejection |
| `adapters.sqlite_ops.sql_measures` / benchmark EXPLAIN | SQL after `-- @compute`; named job/protocol and existing detector constants | raw-event parity, 7/8/10/11 pools, 29/30 attacks, constant pool, actual benchmark plans |
| `SQLiteStore.add_measures` player insert | `job_id,player_key` followed by the fixed `MEASURE_FIELDS`; one positional placeholder per column | exact player set, per-field Python comparison and constraints |
| `adapters.sqlite_audit._insert_rows` | Fixed 22-column staging tuple and generated placeholders; no user identifiers | valid fixture plus invalid state/key/decile/duplicate/NULL cases |
| `adapters.sqlite_audit._row` | `v_observation_funnel`, `v_primary_first_evaluated`, `v_lineage_reachability` enforced allowlist | 13 comparisons with frozen Gold; invalid view rejection |
| `adapters.sqlite_audit._group_rows` | `v_decile_coverage ORDER BY rank_decile`, `v_map_coverage ORDER BY map_name` | empty decile retained; map/rank equality; invalid grouping rejected |
| `SQLiteAudit.calculate` scripts | `sql/v3_audit.sql` split at `-- @load-boundary`; schema then transactional transform | in-memory only; no Gold changes |
| test `read(query)` and child connection | Literal queries and the fixed crash script in `tests/test_ops.py` | included as helper calls/literals/embedded AST, not hidden production paths |
| `operations_walkthrough` count table | Fixed tuple `job,attempt,review_signal,review_case,review_history`; no user-supplied table identifiers | SQLite backup equality, integrity/FK and history assertions in the executable walkthrough |

The operational result grain is one `(job_id, player_key, rule)` signal. Job identity includes the
input, rule protocol, implementation and Python/SQLite version; a new version can produce a new job
and case. Human work is not automatically joined across versions. Synthetic benchmarks explicitly
map keys to generator actor IDs before comparing versions.

`combat_attack(job_id,player_key,attack_id) WHERE event_type='attack'` supports the linked-damage
`EXISTS`. This avoids multiplying damage rows when attacks repeat an ID. Zero attacks retain a
NULL ratio. Skipped observations retain their documented NULLs; the full state predicate uses
`IS TRUE` so SQL UNKNOWN cannot silently pass a CHECK.

`ROW_NUMBER` chooses one first evaluated observation per player in the research audit, and the
latest attempt per job in operational reporting. Research rank deciles include empty strata.
The lineage recursive CTE follows Gold sources, tracks a delimited path, stops cycles and has a
depth cap of 64. It checks lineage consistency, not independent detection accuracy.

Query plans are collected with actual synthetic job/protocol parameters in `measurements.json`.
Plans describe access paths, not measured index benefit. The M2 baseline changes no index or rule.
Changed review queries and their plan evidence are recorded with the final verification bundle.
There is no performance SLO in shared CI.

The synthetic review trace captured 37 bound statements. Case/show/update and history reads use
the relevant primary-key indexes; batch membership uses the covering batch_job key. The optional
filtered list scans case rows and sorts with a temporary B-tree. The walkthrough has three initial
cases, so this is evidence of query shape, not a large-queue latency test. No extra list index was
added without workload evidence. INSERT plans can have no scan rows; their EXPLAIN opcode count
is also retained in local `review-query-plans.json`.

| Table | One row / key | Relationships and missing values |
|---|---|---|
| `batch` | batch_id | Frozen input snapshot, protocol, code and runtime; all required |
| `job` | job_id | One input/version identity; finished/count/hash required only for SUCCEEDED |
| `batch_job` | batch_id + job_id | FK both parents; many batches can reuse one job |
| `attempt` | job_id + attempt_no | FK job; interrupted or unrecorded successful elapsed is NULL |
| `combat_event` | job_id + event_index | FK job; original array index, optional attack/time, damage required for damage event |
| `player_match` | job_id + player_key | FK job; ratio NULL for no attacks; skipped local_z NULL |
| `review_signal` | job_id + player_key + rule | Composite FK player_match; evidence JSON; existing three rules only |
| `review_case` (v2) | case_id, unique signal tuple | Composite FK signal; workflow state independent of REVIEW |
| `review_history` (v2) | case_id + sequence | FK case; creation has NULL from_state, only note action requires text; updates/deletes rejected |
| `run_meta` | run_id | In-memory audit input hashes and protocol |
| `stg_r2_observation` | run_id + observation_id | FK run; unique run/match/player; state-dependent NULL contract |
| `dim_player` | run_id + player_key | FK run; unique run/rank, coherent rank-decile mapping |
| `dim_match` | run_id + match_id | FK run; coherent season/mode/map |
| `fact_r2_observation` | run_id + observation_id | Composite FK player and match; unique run/match/player |
| `artifact` | run_id + artifact_path | FK run; byte/record counts nonnegative; checked SHA |
| `lineage_edge` | run_id + artifact_path + source_path | Composite FK destination artifact; recursive audit follows declared sources |

Operational `input_player` is a temporary connection table keyed by player_key and cleared for
every match. It is not a persisted player directory or a cross-version identity registry.

Source-folder navigation links back to the owner documents from
[src/adapters/README.md](../../src/adapters/README.md) and [sql/README.md](../../sql/README.md).
The refactor moved statements without changing table/index definitions or SQL computation.
Application use cases contain no SQL strings. `cli` remains a reserved historical contract;
current snapshot initiation is owned by the connection contract.

리팩터링 후 같은 schema에서 새 합성 trace 66개 중 SELECT/WITH/INSERT/UPDATE의 서로 다른
실행문 21개를 다시 EXPLAIN/EXPLAIN QUERY PLAN으로 확인했다. 필터 목록 scan·임시 정렬과
단건 PK 접근은 유지된다. 이 2026-10-27 원자료는 `private/refactoring/20261027/review-query-plans.json`이다.

2026-10-29 조회 수명 변경은 SQL 구문과 인덱스를 유지한다. 소유한 transaction만 종료하는
계약과 영향받는 조회의 실행계획 비교는 [batch](operations/batch.md), [review](operations/review.md),
[조회 snapshot 검증](../maintenance/read-snapshot-validation.md)에 연결한다.
