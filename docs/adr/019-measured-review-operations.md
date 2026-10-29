# 019 — Measured local review operations

- Why: Markdown evidence has no durable human workflow; prior RSS excludes exit/report and crash timing can be incomplete.
- What: Freeze a corrected synthetic baseline first, then add a SQLite case/history and CLI; keep REVIEW and all rules unchanged.
- How: Case uniqueness follows signal(job,player,rule); results/case/success and state/history each commit atomically under flock.
- How: New schema only; reject old databases. GNU Time measures run/report; missing post-commit timing stays NULL.
- How: Compare versions by synthetic actor mapping; require crash/replay/backup checks and namespace-isolated CI.
- Trade-off: No automatic migration, web UI, multiwriter service or distributed store; these need separate measured requirements.
- Trade-off: GCP stays blocked until current credit/expiry is verified; alternatives are documented, not executed.
