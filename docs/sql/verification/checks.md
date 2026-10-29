# 검증 전용 SQL 소유 범위

| 계약 ID | 책임 | 입력·효과 | 검증 |
|---|---|---|---|
| benchmark | 성능 harness의 상태·결과·EXPLAIN 조회 | 합성 DB 읽기; actor ID 대응으로 코드 버전 간 비교 | 같은 버전 hash·교차 버전 exact/float tolerance |
| backup | 합성 walkthrough의 backup·integrity·FK·count | 정해진 다섯 table만 count; SQLite backup API 사용 | dump·history·report bytes 일치 |
| test | 테스트 및 공개 SQL 예제 | 격리된 임시 DB; 장애 주입·금지된 변경 포함 | 전체 unittest와 README 질의 목록 |

테스트에 있는 악성·실패 예상 SQL은 운영 허용 구문이 아니다. 원문과 매개변수는
[inventory](../inventory.md), 계약 내용은 [contracts.json](../contracts.json)에 둔다.
실행 지점·helper 호출·고유 정적 텍스트는 서로 다른 집계 단위다. 런타임 SQL 조합의 동등성까지
자동 증명하지 않으므로 새로운 wrapper/동적 식별자는 수동 검토와 새 계약 연결이 필요하다.
[검증 보고서](../../operations-validation.md)는 실제 실행과 미검증을 구분한다.

현재 실행 구문 소유자: [src/adapters/sqlite_benchmark.py](../../../src/adapters/sqlite_benchmark.py).
조회·검증·발행 순서는 [application](../../architecture/clean-architecture.md)이 소유한다.
