# 조회 snapshot 수명 검증 — 2026-10-29

사용자 `implement` 재개로 Python 3.10/3.11/3.12의 전체 오프라인 동작 검증을 마쳤다.
사용자는 고정된 변경 전후 snapshot을 정식 리뷰 기준으로 승인했고, 이번 티켓의 타입 검사는
**미실행으로 명시해 별도 도입 작업으로 분리**했다. 동작 검증과 정식 리뷰는 로컬 완료이며
commit/push는 보류다. 계약은 [DESIGN §12–13](../../DESIGN.md)과
[ADR 024](../adr/024-owned-read-snapshots.md), 현재 범위는 로컬
`.scratch/review-snapshot-lifetime/issues/01-owned-read-snapshots.md`를 따른다.

변경은 `OperationsStore.read_snapshot` port, SQLite의 소유권 판별·종료, Operations의
review/status/report 조회 범위와 CLI의 직접 BEGIN 제거다. 쓰기·schema·SQL 구문·룰·의존성은 유지한다.

| 확인 범위 | 실제 결과와 한계 |
|---|---|
| TDD | 연속 review의 남은 transaction, status의 동시 commit 혼합, report의 중첩 BEGIN을 각각 실패→수정→통과로 기록 |
| 새 SQLite 회귀 | 최초 3.10 전체 실행에서 테스트 콜백 복구 3곳의 오류 4건을 확인했다. 호환 방식으로 수정한 뒤 3.10 단독 6/6 및 아래 세 환경의 전체 검사에서 PASS. 정상·없는 행·DB 오류 뒤 재사용, caller transaction·미커밋 값, 동시 쓰기 snapshot, 발행 전 종료 검증 |
| 전체 오프라인 회귀 | Python 3.10.20 / 3.11.15 / 3.12.3 각각 73/73 PASS, skip 없음. namespace·자식 격리 확인 후 tests→demo→SQL inventory 순서로 exit 0. SQLite는 각각 3.50.4 / 3.50.4 / 3.45.1 |
| 공개 demo | 세 환경 각각 2개 작업 성공·3개 신호·507개 이벤트, 재실행 시 새 attempt 없이 완료 결과 재사용 |
| TESTMATCH | parse→detect→report PASS. AGENTS §2 기대값·마스킹 유지 |
| 이전 코드 DB | 조회·완료 상태·기존 메모/이력 보존, 보고서 4개 SHA 동일. 이전 batch 재개는 BATCH_CODE_CHANGED |
| backup 복원 | SQLite integrity/FK 및 논리 행 동일, 복원 보고서 SHA 동일. 복원된 이전 DB에 새 코드로 note 추가 후 완료 상태·이전 이력 유지 |
| SQL | 20계약, 실행 지점 88·helper 22·정적 text 121·총 항목 245. inventory --check PASS. 테스트의 추가 SQL도 포함하며 고유 운영 질의 수와 다름 |
| 실행계획 | 같은 합성 DB·바인딩으로 이전/현재 adapter의 조회 SQL 12개, EXPLAIN QUERY PLAN과 opcode 수가 동일. 처리 성능 측정 아님 |
| 도식 | D17 원본·SVG·20쪽 HTML/PDF 갱신, 다른 SVG 19개 byte 동일. 최초에는 D17만 확인했으며 정식 리뷰 후 같은 PDF의 20쪽 모두를 96dpi 원본 크기로 육안 확인해 글자·폰트·겹침·잘림 문제를 발견하지 않음 |
| 보존 | 재개 후 동결 연구 837 SHA 동일. PLANNING·DESIGN §4·schema·의존성·원 명세 유지. 티켓의 runtime 변경 파일은 4개이며 이번 재개에서는 runtime을 변경하지 않음 |

코드 지문은 `1bb63d3dc00cc0bd484a71f3ed5192370f8ac07a038daefdf8526bfc75a0006d`에서
`6f7b70b238c1b370c1f94b50937efb37b2f3c0a62aa6b875e80f804cf1b44778`로 바뀌었다.
식별자 계산식은 유지하며 다른 코드의 기존 batch를 실행 재개하지 않는 기존 계약을 확인했다.

원자료는 로컬 `private/refactoring/20261029-read-snapshots/README.md`가 역할별로 연결한다.
`compatibility-after.json`, `read-query-plans.json`, `diagram-verification.json`, `preservation.json`을
근거로 삼는다. Git clone만으로 이 로컬 원자료가 복원되지는 않는다.

재개 후 최종 근거는 로컬
`private/refactoring/20261029-read-snapshots/resume-20261029T004439412960Z-verified/`의
`matrix.json`, `offline-310/311/312.log`, `targeted-310.log`, `preservation.json`이다.
수정 전 실패는 별도 `resume-20261029T004439412960Z/`에 보존했다. 최초 3.10 실패를
3.11·3.12의 성공으로 상쇄하지 않고, 수정된 테스트로 세 환경을 모두 다시 통과했다.

테스트의 `set_authorizer(None)`은 Python 3.11부터 지원되는 방식이었다
([Python 공식 문서](https://docs.python.org/3.11/library/sqlite3.html#sqlite3.Connection.set_authorizer)).
오류·동시 쓰기 주입 뒤 `SQLITE_OK`를 반환하는 callback으로 복구하도록 세 곳을 바꿨다.
같은 연결의 재사용과 transaction 소유권 assertion을 유지했으며 테스트를 제외하지 않았다.

## 정식 리뷰와 검사 범위

위 73개 결과는 현재 변경으로 새로 실행한 값이며 이전 67개 기록을 재사용하지 않았다.
1M/10M 성능은 재측정하지 않았으며
새 최적화는 없다. 최초 인계 때 PDF의 나머지 19쪽은 개별 육안 재검사하지 않았으나,
정식 Standards 리뷰에서 이 절차 누락을 발견해 같은 PDF 20쪽 전체를 확인했다.
이전 D17 렌더의 Type 3 glyph bounding-box 경고는 원 로그에 보존했다. 이번 20쪽 렌더는
exit 0·경고 0건이며 모든 쪽의 시각 확인을 완료했다.
GCP·원격 CI·독립 외부 복원은 미검증이다.

| 항목 | 근거 | 현재 처리 |
|---|---|---|
| 정적 타입 검사 | 설정 및 mypy/pyright/basedpyright 도구 없음을 재확인 | 사용자 지시로 이번 티켓은 NOT RUN으로 기록하고 별도 도입 작업으로 분리. 동작 테스트 통과를 타입 검사 PASS로 바꾸지 않음 |
| 정식 code-review 스킬 | 기본 Git ref 방식 대신 고정된 before-source와 현재 snapshot을 비교하도록 사용자가 명시 승인 | Standards와 Spec을 독립 리뷰. Spec 발견 0건. Standards의 PDF 전체 시각 확인 누락 1건은 후속 검증·문서 보완을 독립 리뷰어가 대조해 해소했으며 남은 발견 0건 |

스킬 원문: `/home/k/.codex/plugins/cache/mattpocock/mattpocock-skills/1.3.1/skills/engineering/code-review/SKILL.md`.
요구 문구는 “If they didn't specify one, ask for it.”와 “confirm … the diff is non-empty.”다.
이전에는 보존용 before-source 비교를 정식 리뷰로 간주하지 않았다. 이후 사용자 명시 승인으로
그 고정 snapshot을 정식 리뷰 비교 기준으로 사용했으며 hash·비어 있지 않은 diff를 확인했다.
원 스킬 파일이나 이전 snapshot·로그는 변경하지 않았다.
commit/push·원격 이슈 생성·클라우드 변경은 수행하지 않았다.

정식 리뷰와 PDF 후속 근거는 로컬
`private/refactoring/20261029-read-snapshots/formal-review-20261029T045254813713Z/`의
`README.md`, `standards-initial.md`, `standards-followup.md`, `spec.md`, `pdf-visual-review.json`, `pdf-render.json`과
`pdf-pages/page-01.png`부터 `page-20.png`까지다.
검사 PDF의 SHA-256은 `b935aae9c8f78d31550ace2ce1b9acdfba01ce6e8e4c9b735de92e0afdbb3df3`로
리뷰 대상과 같으며 PDF·도식·운영 코드를 수정하지 않았다.
