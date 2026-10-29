# 사람 검토 SQL 소유 범위

| 계약 ID | 구문 책임 | NULL·중복·원자성 | 검증 |
|---|---|---|---|
| review-read | batch/state 목록, case+signal 조회, sequence 순 이력 | EXISTS membership으로 중복 제거; 없는 case 거부; creation만 from_state NULL | 모든 CLI·필터·없는 batch/case |
| review-write | start/note/complete/reopen; current state와 이력 | writer lock + BEGIN IMMEDIATE; 동일 commit; sequence는 case별 증가; 잘못된 전이 거부 | 저장/commit 전후 강제 종료·중복 재실행·명시적 retry |

구문별 원문·바인딩·코드 링크는 [inventory](../inventory.md)의 위 계약 ID로 찾는다.
전체 계약은 [contracts.json](../contracts.json), schema DDL과 초기 case 생성은
[배치 소유 범위](batch.md)에 둔다. 이 문서에 복제하지 않는다.

case는 signal(job_id, player_key, rule)에 유일하게 연결한다. 업무 완료는 탐지 어휘 REVIEW를
바꾸지 않는다. note는 이력만 추가하고 현재 상태는 유지한다. 완료 상태도 note가 가능하다.
operator는 로컬 작업자가 제공한 label이며 인증된 주체라는 의미가 없다.

실제 합성 trace 37개 구문과 EXPLAIN/EXPLAIN QUERY PLAN은 로컬 review-query-plans.json에 있다.
단건 조회·변경은 PK, batch 필터는 batch_job covering key를 사용한다. 목록은 scan과 임시 정렬을
사용하며 대규모 큐 부하를 측정하지 않았으므로 추가 인덱스의 효과를 주장하지 않는다.
[검토 ERD·상태](../../architecture/D07.svg), [원자성 테스트](../../../tests/test_ops_review.py)를 함께 본다.

현재 실행 구문 소유자: [src/adapters/sqlite_ops.py](../../../src/adapters/sqlite_ops.py).
조회·검증·발행 순서는 [application](../../architecture/clean-architecture.md)이 소유한다.

목록의 batch 확인과 case 조회, 상세의 signal과 history 조회는 각각 하나의
`OperationsStore.read_snapshot()` 안에서 실행한다. transaction이 없으면 시작하고
정상·없는 행·DB 오류 모두에서 종료한다. caller의 기존 읽기·쓰기 transaction은 재사용하며
commit/rollback하지 않는다. 동일 service의 재조회와 미커밋 값 보존은
[조회 수명 회귀](../../../tests/test_ops_snapshots.py)가 실제 SQLite 연결로 검증한다.

리팩터링 후 같은 schema에서 새 합성 trace 66개 중 SELECT/WITH/INSERT/UPDATE의 서로 다른
실행문 21개를 다시 EXPLAIN/EXPLAIN QUERY PLAN으로 확인했다. 필터 목록 scan·임시 정렬과
단건 PK 접근은 유지된다. 이 2026-10-27 원자료는 `private/refactoring/20261027/review-query-plans.json`이다.

2026-10-29 조회 수명 변경의 SELECT와 실행계획 비교는
[조회 snapshot 검증](../../maintenance/read-snapshot-validation.md)에 연결한다.
SQL 구문·값 바인딩·인덱스는 변경하지 않았다.
