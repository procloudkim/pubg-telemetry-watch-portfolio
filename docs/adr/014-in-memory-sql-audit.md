# ADR 014, in-memory SQL audit

- Why 문제: JSON과 Python 파이프라인만으로는 관계형 모델링과 복합 SQL 처리 근거가 보이지 않는다.
- What 결정: 완료된 v3 Silver, Gold와 manifest를 SQLite `:memory:` audit consumer로 투영한다.
- How 구현: PK, FK, CHECK, 조건부 집계, window function과 재귀 CTE를 `sql/v3_audit.sql`에 둔다.
- How 검증: SQL 분모, 첫 evaluated 표본, map과 rank decile을 동결 Gold와 교차검증한다.
- How 계보: manifest artifact 631개와 lineage edge 721개를 적재하고 cycle 0을 확인한다.
- 기각한 대안: 운영 RDBMS와 DuckDB는 현 데이터 규모에서 새 인프라 또는 의존성만 추가한다.
- Trade-off: SQLite는 분산 처리와 운영 저장소 경험을 증명하지 않으며 SQL 검증 범위만 증명한다.
- 경계: API, 원시 데이터, Gold, 룰과 임계값은 변경하지 않는다.
