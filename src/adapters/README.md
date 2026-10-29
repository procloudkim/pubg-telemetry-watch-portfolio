# Adapter ownership and SQL navigation

Application ports define the required operations. These implementations own resource access;
callers compose them in `src/cli`. SQL values are bound, and schema/view/column identifiers come
from finite internal contracts. This index links the source folder back to its SQL documentation.

| Source | Sole SQL document owner |
|---|---|
| [sqlite_ops.py](sqlite_ops.py): connection, registration, work, results, status, report | [Batch](../../docs/sql/operations/batch.md) |
| [sqlite_ops.py](sqlite_ops.py): review reads, state and history writes | [Review](../../docs/sql/operations/review.md) |
| [sqlite_audit.py](sqlite_audit.py): in-memory reconstruction and fixed views | [Research audit](../../docs/sql/research/audit.md) |
| [sqlite_benchmark.py](sqlite_benchmark.py): actor mapping and EXPLAIN | [Verification](../../docs/sql/verification/checks.md) |

[Inventory](../../docs/sql/inventory.md) resolves every statement to module, `Class.method`,
line and contract; [contracts](../../docs/sql/contracts.json) record grain, NULL/duplicate meaning,
transactions, indexes and tests. [Architecture](../../docs/architecture/clean-architecture.md)
also covers files, credentials, HTTP, clocks, RDF and presentation adapters.
