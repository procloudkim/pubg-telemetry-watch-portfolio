# 배치 SQL 소유 범위

이 문서는 운영 schema·연결·job 처리·report SQL을 소유한다. 각 구문의 원문·코드 위치·매개변수는
[전수 목록](../inventory.md), 구문별 계약 ID의 상세 의미는 [contracts.json](../contracts.json)이 정본이다.
사람 작업의 조회·변경 SQL은 [review](review.md)가 소유한다. 공유 table DDL은 이 문서에 한 번만 속한다.

| 계약 ID | 처리 경계 | 검증과 해석 |
|---|---|---|
| connection, ops-schema | 빈 DB만 schema v2 초기화; FK/WAL/FULL; temp input_player | 기존 schema 거부 시 파일 불변, PK/FK/CHECK/trigger 검사 |
| registration, batch-read | immutable batch·job identity·membership | 중복 등록은 기존 성공을 재사용; metadata 불일치 거부 |
| work, recovery, retry | 단일 writer claim·중단 복구·명시적 retry | 이전 attempt를 보존하며 실패 작업만 재큐잉 |
| processing | combat·player·signal·case·job 성공을 한 commit에 저장 | commit 전후 종료, SQL parity 실패, DB 오류; 지연은 commit 후 별도 저장 |
| ops-compute | 원시 전투 projection의 R2 검산 | 중복 attack은 EXISTS로 판정; 0분모 NULL; pool/attack 경계 검사 |
| status, report, cli | batch 상태·완료 결과·발행 경계 | 완료 결과만 발행; report 재발행은 사람 기록을 변경하지 않음 |

`status`는 batch·job·attempt를 같은 snapshot에서 읽는다. `report`가 호출한 status와
후속 결과 조회도 같은 snapshot을 공유한다. 조회가 직접 시작한 transaction은 오류 시에도
종료하며 report의 파일 발행 전에 끝난다. caller의 기존 읽기·쓰기 transaction은 재사용하고
commit/rollback하지 않는다. `cli`는 과거 계약 ID로 보존하며 현재 직접 실행 SQL은 없다.
CLI의 connection 수명과 application의 조회 범위, adapter의 transaction 소유권을 분리한다.

값은 SQLite 바인딩으로 전달한다. 동적 열 이름은 내부 고정 MEASURE_FIELDS에서만 만든다.
전체 테이블 grain·NULL·인덱스 설명은 [목록 안내](../README.md)를 함께 본다.
실행계획은 실제 합성 job/protocol 매개변수의 measurements.json에 보존한다.
[운영 ERD](../../architecture/D05.svg)와 [복구 흐름](../../architecture/D08.svg)이 이 계약을 요약한다.

현재 실행 구문 소유자: [src/adapters/sqlite_ops.py](../../../src/adapters/sqlite_ops.py).
조회·검증·발행 순서는 [application](../../architecture/clean-architecture.md)이 소유한다.

조회 수명 변경의 동시 쓰기·예외·실행계획 비교는
[조회 snapshot 검증](../../maintenance/read-snapshot-validation.md)과
[실제 SQLite 회귀](../../../tests/test_ops_snapshots.py)를 따른다.
