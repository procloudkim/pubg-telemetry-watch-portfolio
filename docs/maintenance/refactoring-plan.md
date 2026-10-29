# 후속 전체 리팩터링 계획

상태: 구현·로컬 검증 완료, 2026-10-27 사용자 승인으로 별도 브랜치
`refactor/clean-architecture`에서 수행했다. 이전 미커밋·미추적 변경과 동결 산출물은 보존했다.
기존 62개 gate에 계층·소스 지문·SQL 경계 검사를 더해 세 Python runtime에서 67개 gate를 통과했다.
전후 32회 성능과 결과 parity, 기존 schema-v2 DB 호환, 복구·검토·backup을 확인했다.

정본은 [구현 아키텍처](../architecture/clean-architecture.md), [검증 결과](refactoring-validation.md),
[개별 성능값](refactoring-performance.md)이다. 시작 소스 109개·동결 837개 hash와 실제 실행 증거는
로컬 `private/refactoring/20261027/`에 보존한다. GCP·원격 CI는 이 로컬 완료와 구분한다.

조회·시각화 우선순위는 REVIEW 근거 → 검토/복구 이력 → 운영 지표 → 2D 리플레이다.
계산·조회 use case·SQL adapter·표현을 분리해 CLI와 향후 UI가 검증된 결과를 공유한다.
protocol·출처·분모·결측과 이벤트/처리/검토 시각을 구분한다. 현재 R1 끝점은 전체 경로가 아니며
전체 replay는 별도 데이터 계약이 필요하다. 새 UI·다른 게임 지원은 구현하지 않았다.

## 범위와 보존 계약

전체 Python 소스·테스트·SQL·CLI·설정·문서를 함께 점검하되 동결 연구 산출물은 읽기만 한다.
PLANNING §5, DESIGN §4의 근거, 룰·임계값·REVIEW 어휘·원 연구 분모는 변경하지 않는다.
기존 CLI·오류 코드·보고서 byte·원자성·재시도·검토 이력·schema 거부 계약을 보존한다.
파일 이동도 job fingerprint에 영향을 준다. 이전 job을 새 코드로 자동 재개하거나 사람 case를
버전 간 자동 병합하지 않고, 합성 actor 대응 비교로 결과 정합을 검증한다.

## 수행 순서와 완료 증거

| 단계 | 작업과 책임 | 채택 증거 |
|---|---|---|
| R0 완료 | 실제 import/호출/입출력 지도, 변경 전 source·frozen hash·tests 확보 | 누락 없는 영향 목록, 별도 브랜치, 재현 가능한 기준선 |
| R1 완료 | parse/detect의 순수 계산과 review 전이 규칙을 domain으로 분리 | domain의 CLI/SQLite/네트워크 import 0, 기존 결과 parity |
| R2 완료 | register/run/retry/review/report를 application use case로 분리 | 트랜잭션 경계 보존, 외부 adapter를 우회하는 쓰기 0 |
| R3 완료 | SQLite·manifest/파일·clock을 adapter로 옮김; 실제 대체 지점에만 interface | DB 오류·중단·checksum·동시 writer·backup gate 유지 |
| R4 완료 | CLI는 인수 검증·호출·출력만 담당; research/fetch와 ops 진입점 분리 | 기존 명령/exit/고정 오류 JSON 호환, network namespace 검사 |
| R5 완료 | 중복 helper·불명확 이름·오래된 주석 정리, SQL·도식·설계 동시 갱신 | 소유권/SQL coverage/링크 검사, 전체 3.10/3.12 회귀 |
| R6 완료 | 새 고정 환경 baseline과 교차 버전 결과 비교, 보안 재검토 | 성능·메모리 회귀 설명, 미확인 결과와 blocker 기록 |

구현 의존성은 `CLI → application → domain`, `adapters → application ports/domain`이다.
domain은 외부 자원이나 전역 설정을 읽지 않는다. port는 실제 의존성 경계에만 도입하고
범용 repository/framework를 미리 만들지 않는다. 구현 폴더는 `src/domain`, `src/application`,
`src/adapters`, `src/cli`다. 기존 `src/*.py`는 호환 진입점으로 유지했다.
[D13](../architecture/D13.svg)은 구현 경계를, D16–D20은 계산·조회·audit·호환·검증을 연결한다.

## 보안·문서 규칙

입력 검증은 CLI/파일/DB 경계에서, 업무 규칙은 domain에서 담당한다. SQL 값 바인딩과
고정 식별자 목록, 경로 containment, 같은 byte checksum, atomic write, 고정 오류 코드,
credential 비노출을 보존한다. 메모는 자유 입력이므로 출력 형식별 escape와 비밀정보 취급을
검토한다. 주석은 trust boundary·트랜잭션·복구 이유에만 붙이고 코드 설명을 중복하지 않는다.
SQL 계약 ID의 MECE 소유 구조와 source 링크를 유지하며, 구조 결정마다 10줄 이내 ADR을 쓴다.

의존성 추가·schema migration·룰 변경·새 네트워크 수집은 이 리팩터링 계획의 승인이 아니다.
blocker가 생기면 해당 단계를 멈추고 사실·영향·해소 조건·미실행 대안을 기록한다.
큰 일괄 재작성은 회귀 원인을 분리하기 어려워 채택하지 않는다. 단계별 검증 후 다음 단계로 간다.

## 보류한 별도 범위

GCP의 현재 크레딧·정확한 만료·API·자원 목록/종료 조건은 기존 blocker를 유지한다.
원격 CI는 commit/push 보류 상태에서 실행하지 않았다. 유료 업그레이드·VM 생성·삭제·예약,
실제 API 수집, UI, 전체 replay, 다른 게임 지원은 수행하지 않았다. 해소 조건과 미실행 대안은
[검증 결과](refactoring-validation.md#미검증과-blocker)에 정리했다.
