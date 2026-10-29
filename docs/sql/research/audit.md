# 동결 연구 audit SQL 소유 범위

| 계약 ID | 책임 | 관계·NULL·트랜잭션 | 검증 |
|---|---|---|---|
| audit-schema | sql/v3_audit.sql의 schema·transform·view | in-memory DB만 사용; PK/FK/UNIQUE/CHECK IS TRUE | 잘못된 상태·NULL·rank·중복·dimension 거부 |
| audit-load | staging 입력과 schema/load boundary 실행 | 고정 22열 바인딩; transform transaction; 원 Gold 변경 없음 | 원 Gold와 13개 지표 비교 |
| audit-read | _row/_group_rows의 다섯 view 조회 | 빈 decile 보존; first evaluated 1개; lineage cycle와 depth 64 제한 | funnel·primary·decile·map·lineage 대조 |

구문별 위치·표현식은 [inventory](../inventory.md), 각 계약의 상세 내용은
[contracts.json](../contracts.json), 구조는 [연구 ERD](../../architecture/D06.svg)에 있다.
동적 view 식별자는 코드 내부의 유한 목록이다. 사용자 SQL이나 경로를 식별자로 보간하지 않는다.
audit는 기존 결과의 정합성 검사이며 독립 탐지 정확도 평가가 아니다.
SPARQL은 별도 언어라 이 SQLite 소유 범위에 포함하지 않는다.

현재 실행 구문 소유자: [src/adapters/sqlite_audit.py](../../../src/adapters/sqlite_audit.py).
조회·검증·발행 순서는 [application](../../architecture/clean-architecture.md)이 소유한다.
