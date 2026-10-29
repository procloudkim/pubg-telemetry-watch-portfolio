# SQL source ownership

| Source | Contract owner | Runtime caller |
|---|---|---|
| [ops.sql](ops.sql) | [Operational schema and computation](../docs/sql/operations/batch.md) | [sqlite_ops](../src/adapters/sqlite_ops.py) |
| [v3_audit.sql](v3_audit.sql) | [Research schema, transform and views](../docs/sql/research/audit.md) | [sqlite_audit](../src/adapters/sqlite_audit.py) |

Inline Python statements are also included in the [complete inventory](../docs/sql/inventory.md).
The [owner partition](../docs/sql/owners.json) assigns each contract exactly once. Run
`python tools/sql_inventory.py --check` after changes; do not treat execution points as distinct
queries. The refactor preserves both SQL files, schema version and indexes.
