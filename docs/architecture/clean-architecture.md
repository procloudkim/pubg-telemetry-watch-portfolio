# 실행 코드의 책임과 의존성

기존 `python -m src.<명령>`은 유지한다. 호환 진입점은 CLI와 composition을 호출하고,
업무 순서·계산·외부 자원·표현의 구현은 아래 계층이 소유한다. 결정은
[ADR 022](../adr/022-clean-architecture-boundaries.md), 검증은
[리팩터링 결과](../maintenance/refactoring-validation.md)에 기록한다.

```text
src/
├── domain/                 # 입력값만으로 계산; 외부 자원·현재 시각 없음
│   ├── pubg/               # parsing, detection, privacy, API payload selection
│   ├── review.py           # 사람 업무 상태 전이; REVIEW 판정과 구분
│   ├── operations.py       # PUBG combat projection, SQL parity, 운영 집계
│   ├── research.py         # cohort, 분모, 통계, 품질 판단
│   ├── graph.py            # 관계·lineage 투영과 정합성
│   ├── audit.py            # SQL 결과와 Gold 대조
│   ├── semantic.py         # protocol 및 competency query 기대값
│   └── identity / ledger / quality / serialization / synthetic / tokens / errors
├── application/            # 실행 순서·조회·트랜잭션·발행 정책
│   ├── ports.py            # 실제 파일·DB·HTTP·시계·engine 경계만 선언
│   ├── workspace.py        # I/O 없이 구성하는 논리 경로
│   ├── operations.py       # register, work, retry, review, status, report
│   ├── pipeline.py         # 기존 v1 parse/detect/report
│   ├── collection.py       # v1/v2 수집 예산과 순서
│   ├── research.py         # v3 원장·preflight·고정 cohort·평가
│   ├── medallion.py        # 기존 자료 이관·검증·manifest
│   ├── graph_audit.py / sql_audit.py / semantic.py
│   └── demo.py             # 운영 use case로 합성 시연
├── adapters/               # SQLite, files, HTTP, RDF, 표현, 시계, provenance
├── cli/                    # 인수·출력·exit code·resource 생성/종료
└── 기존 *.py               # 공개 함수와 명령의 얇은 호환 진입점
tools/                      # 성능·walkthrough·오프라인·문서 검증 도구
sql/                        # 기존 schema/계산 SQL; Python 내장 SQL은 adapter 소유
tests/                      # 기존 시나리오와 경계·보안 회귀
```

| 경계 | 의존 규칙 | 실행 소유자 |
|---|---|---|
| Domain | 표준 라이브러리의 순수 계산과 다른 domain만 참조 | PUBG 규칙, cohort, 상태, 결과 비교 |
| Application | domain·다른 use case·port 참조; SQL 문자열/연결/직접 I/O 없음 | commit 순서와 발행 여부 |
| Adapter | application port와 domain을 구현/사용; CLI에 역참조하지 않음 | 외부 자원의 실제 동작 |
| CLI/composition | 구체 adapter를 생성해 use case에 전달 | 파일 경로·DB 수명·writer lock·오류 출력 |
| 호환 진입점 | 기존 호출을 새 구현으로 전달 | 기존 명령·함수의 인수/반환 형태 |

`Protocol`은 런타임 프레임워크가 아니다. SQLite 연결은 `SQLiteStore` 안에 두고,
application은 이름 있는 연산과 transaction port를 사용한다. SQL 값은 바인딩하며 열·view
식별자는 고정 목록이다. 구체 구현의 SQL은 [MECE 소유 트리](../sql/README.md)가 관리한다.

## 유지한 실행 경계

| 작업 | 순서와 원자성 |
|---|---|
| Job 처리 | claim commit → 결과 transaction → signal/case/SUCCEEDED commit → 별도 계측 저장 |
| 처리 실패 | 결과 rollback; 정상 job과 실패 job 구분; DB I/O 오류는 worker 중단 |
| 중단 복구 | 동일 writer lock으로 이전 worker 종료 확인; INTERRUPTED 이력 보존 후 재개 |
| 사람 검토 | 전이 검증 → current state와 append-only history를 같은 commit에 저장 |
| 검토·상태 조회 | snapshot 시작 또는 기존 transaction 재사용 → 모든 결과 읽기 → 직접 시작한 transaction만 정상·예외 시 종료 |
| 보고서 | status와 결과를 같은 snapshot에서 읽기 → 직접 시작한 snapshot 종료 → 표현·atomic 파일 쓰기 → 완료 manifest를 마지막에 발행 |
| 연구 수집 | durable reservation → HTTP → completion 원장; 미확인 요청도 예산에 포함 |
| 연구 audit | 동결 자료 읽기 → 독립 graph/SQL 검산 → RDF/SHACL → write-once 발행 |

오류 주입은 호환 모듈의 오래된 alias가 아니라 실제 `sqlite_ops`, `BatchInputs`, `LocalFiles`,
`PubgHttp`, `SystemClock` 경계에 적용한다. 기존 crash 자식 프로세스도 해당 경계를 사용한다.

`OperationsStore.read_snapshot()`이 기존 transaction 유무를 adapter 안에서 판별한다.
Application은 조회 범위를 정하고 CLI는 connection 수명만 관리한다. 중첩 status는 report의
snapshot을 종료하지 않는다. caller가 이미 연 읽기·쓰기 transaction을 빌렸다면 오류가 나도
use case가 commit/rollback하지 않으며, report 파일 발행 중에도 종료 책임은 caller에게 있다.
결정은 [ADR 024](../adr/024-owned-read-snapshots.md), 실제 SQLite 동시 쓰기·예외·호환 검증은
[조회 snapshot 검증](../maintenance/read-snapshot-validation.md)에 기록한다.

## 검증된 조회와 향후 표현

| 조회 | 현재 반환하는 근거 | 재사용 경계 |
|---|---|---|
| `Operations.review_list` | batch/state로 필터한 case | 동일 DB 읽기 snapshot |
| `Operations.review_show` | case, signal의 rule protocol·근거, 순서 있는 사람 이력 | 탐지 재실행 없음 |
| `Operations.status` | job/attempt 상태, 실패·재시도·측정 표본 수 | 저장된 결과를 집계 |
| `SqlAudit.read` | frozen Gold와 대조한 SQL 요약 | 보고서를 쓰지 않는 조회 |
| `GraphAudit.analyze_run` | 관계·lineage·검사 결과 | 파일 읽기와 순수 투영을 분리 |
| `Operations.report` | 완료 결과·source/result SHA를 포함한 manifest와 보고서 | 파일을 발행하는 명령 |

향후 UI는 **REVIEW 근거 → 검토/복구 이력 → 운영 지표 → 2D replay** 순서로 이 조회를
재사용한다. protocol·출처 hash·분모·결측·단위를 함께 표시하고, telemetry 이벤트 시각,
job 처리 UTC, 사람 검토 UTC를 혼합하지 않는다. source SHA는 현재 report manifest의 job
provenance에 있다. 검토 완료는 사람 업무 종료이며 탐지 판정을 변경하지 않는다.

현재 `combat_event`는 공격/피해만 보존한다. R1 근거의 시작·끝 좌표는 전체 이동 경로가
아니므로 보간한 경로를 실제 관측처럼 표현하지 않는다. 전체 replay에는 별도 위치 데이터
계약이 필요하다. UI·다른 게임 지원·추가 API 수집은 구현하지 않았다.

## 유지보수 규칙

`tests/test_architecture.py`는 계층 역참조·순환 import·core의 직접 자원 호출과 중첩 파일
fingerprint 누락을 검사한다. 정적 검사는 완전한 데이터 흐름 증명이 아니므로 실제 장애·복구
검사와 함께 채택한다. 새 SQL 메서드는 `Class.method`까지 inventory에 나타나며 계약과
소유 문서를 하나씩 연결해야 한다. schema/룰/의존성 변경은 별도 승인 범위다.

코드 fingerprint는 정렬한 `src/**/*.py`와 `sql/**/*.sql` 전체다. 코드가 달라진 기존 batch는
실행 재개를 거부하지만 schema v2의 조회·검토·report는 유지한다. 버전 사이 job/case를 자동
병합하지 않는다. 합성 성능 비교만 actor ID를 대응시키고 float에는 기존 1e-9 허용오차를 쓴다.

도식: [계층 D13](D13.svg), [PUBG 경계 D16](D16.svg), [조회 D17](D17.svg),
[연구 audit D18](D18.svg), [버전 호환 D19](D19.svg), [채택 gate D20](D20.svg).
