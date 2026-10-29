# ADR 024 — 조회 snapshot의 소유자만 종료
- Why: 연속 검토 조회가 transaction을 남겨 실패하고 직접 호출한 status는 서로 다른 시점의 데이터를 섞을 수 있었다.
- What: review list/show·status·report는 자신이 시작한 읽기 transaction만 정상·예외 모두에서 종료한다.
- How: OperationsStore.read_snapshot port와 SQLite adapter의 context manager로 기존 transaction을 재사용한다.
- How: report 내부 status는 같은 snapshot을 공유하며 직접 연 snapshot은 파일 발행 전에 종료한다.
- 경계: caller의 기존 읽기·쓰기 transaction과 미커밋 변경은 보존하고 종료 책임도 caller에게 남긴다.
- 보존: schema v2·쓰기 원자성·룰·식별자 계산·CLI 계약은 유지한다.
- 기각: 무조건 BEGIN은 중첩 조회를 깨고, 무조건 rollback/commit은 caller의 미커밋 작업을 잃거나 확정한다.
- Trade-off: caller가 긴 transaction을 전달하면 파일 발행 중 수명도 caller가 관리해야 한다.
- 검증: 실제 SQLite 재사용·동시 쓰기·예외 회귀 및 이전 DB 호환은 ../maintenance/read-snapshot-validation.md.
