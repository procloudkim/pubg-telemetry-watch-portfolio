# 1~2일 컷

> **2026-10-29 조회 snapshot 로컬 완료:** 세 Python 환경 각각 73개 tests·demo·SQL inventory·namespace/자식 격리와 동결 837 SHA PASS. 사용자가 승인한 고정 snapshot의 정식 리뷰는 Spec 발견 0건, Standards의 PDF 확인 누락 1건 해소 후 잔여 0건이다. [검증 결과](docs/maintenance/read-snapshot-validation.md)와 [정식 리뷰 근거](private/refactoring/20261029-read-snapshots/formal-review-20261029T045254813713Z/README.md)를 따른다. 타입 검사는 사용자 지시로 NOT RUN·별도 도입 작업으로 분리했고 로컬 티켓은 ready-for-human이다. commit/push·원격 CI·cloud 보류는 유지한다. 이전 [HANDOFF](private/refactoring/20261029-read-snapshots/HANDOFF.md)와 [전체 회귀 원자료](private/refactoring/20261029-read-snapshots/resume-20261029T004439412960Z-verified/README.md)는 당시 기록으로 보존한다.

> **2026-10-29 티켓 발행 완료:** 사용자 확인으로 [01 조회 snapshot 수명](.scratch/review-snapshot-lifetime/issues/01-owned-read-snapshots.md)을 로컬 tracker에 발행했다. `ready-for-agent`, 선행 티켓 없음, 완료 기준 8개다. 최신 범위는 이 티켓을 따르며 원래 명세·제안·과거 checkpoint는 당시 상태로 보존한다. 애플리케이션 구현은 시작하지 않았다.

> **2026-10-28 체크포인트·후속 스킬:** [새 세션 인계](private/planning/2026-10-28-session/HANDOFF.md)와 해당 경로의 `checkpoint.json`에 최신 상태·보존 검사·미해결 질문을 기록한다. 사용자 재개 뒤 로컬 Markdown 스킬 설정을 확인받아 적용했고, 아키텍처 검토에서 동일 Operations 인스턴스의 연속 조회 실패를 재현했다. 사용자는 후보 01과 transaction 소유권 계약에 동의했으며 최종 구현 범위 공유 확인을 대기 중이다. 기존 GCP·DB 선택·원격 반영 보류는 유지한다.

> **2026-10-28 DB 선택 사실 확인:** [로컬 문서 조사·사용자 제공 계정 정보](private/planning/2026-10-28-gcp-db-facts.md)를 먼저 읽는다. 현재 문서/코드는 SQLite 유지로 확인됐으나 사용자가 기억하는 PostgreSQL 확정 지시는 찾지 못했다. DB 선택 차이를 임의로 해석해 배포하지 않는다. 평가판 유형·잔액·남은 일수는 사용자 확인값을 받았고 정확한 만료 시각은 별도 미확인이다.

> **2026-10-28 GCP 조회 재개:** 사용자 재개 및 Asset API 활성화 시도 후, 기존 인증 경로와 정확한 프로젝트를 확인해 API 활성화·자원 검색을 검증했다. [후속 관측·재현 명령](private/cloud-retirement/20261101/evidence/20261028-auth-asset/README.md)을 따른다. 전체 조사·클라우드 재현·종료 준비는 BLOCKED이며 삭제·예약·원격 반영은 진행하지 않았다.

> **2026-10-27 세션 종료:** 사용자 요청으로 [다음 세션 handoff](private/refactoring/20261027/HANDOFF.md)를 저장했다. 로컬 완료·증거 위치·미커밋 상태·blocker·재개 조건을 이어받고, 다음 사용자 지시 전 추가 작업을 시작하지 않는다. 기존 검증 묶음은 보존하며 종료 인계로 변경된 PLAN/LOG는 별도 기록한다.
> 후속 요청의 [/tmp 중요 정보 색인](private/refactoring/20261027/tmp-context/README.md)은 재현 자료·검증 근거·실행 문맥을 MECE하게 연결한다. 최신 종료 문서 검증은 해당 경로의 `verification.json`을 따른다.

> **2026-10-27 리팩터링 로컬 완료:** `refactor/clean-architecture`에서 domain/application/adapters/cli·기존 호환 진입점을 구현했다. Python 3.10/3.11/3.12 각각 67개 오프라인 회귀, 전후 32회 actor parity, 기존 DB/report/사람 이력 호환·복원, 동결 837 SHA를 확인했다. [검증 결과](docs/maintenance/refactoring-validation.md)와 [성능 원자료 안내](docs/maintenance/refactoring-performance.md)를 따른다. GCP/원격 CI·commit/push는 기존 보류 범위를 유지한다.

> **main 인계 — 2026-10-27 별도 대화의 후속 지시:** GCP 작업 재개 전 [클라우드 종료 통합 참조](private/cloud-retirement/20261101/README.md)를 먼저 읽는다.
> 삭제 범위는 **지정 프로젝트 전체(기존 리소스 포함)**, 기한은 **2026-11-01 23:00 KST**다. 이전의 “새 자원만 정리” 범위는 이 프로젝트에 한해 대체됐다.
> 현재 종료 작업은 **BLOCKED / 삭제·자동 예약 미실행**이다. blocker는 우회하지 않고 보고하며 대안은 문서화한다. 증빙 촬영·외부 반출·복원과 보안 조건은 연결 문서를 따른다.
> main은 2026-10-27 14:48 KST 통합 참조·실행 계약·blocker를 열람했다. 아래 인수 확인에 다음 조치를 기록했으며 삭제·예약은 계속 미실행이다.

> **2026-10-27 이전 운영 기능 완료 기록:** 로컬 M0~M6의 구현·32회 측정·62개 회귀(3.10/3.11/3.12)·도식·SQL 문서·증거 묶음 복원을 완료했다. 성능 개선의 인과 해석·원격 CI·M7/M8은 아래 blocker를 따른다. 작업 브랜치는 `feat/gcp-staging-architecture-sql`, commit/push는 미실행이다. 이 시점에 계획으로 남긴 리팩터링은 이후 사용자 승인으로 실행했으며 최상단 최신 기록을 따른다.

> **2026-09-10 종료:** 로컬 배치 구현·검증 완료, 변경은 미커밋 상태다. 원격은 기존 버전이며 반영과 이력 정리는 `PAUSED_BY_USER`를 유지한다. 오늘은 문서 정리로 종료하며 다음 사용자 지시 전 추가 작업을 진행하지 않는다. 최신 검증 근거와 재개 지점은 아래 로컬 배치 항목에 있다.

- [x] developer.pubg.com 키 발급 (사용자, 5분) → .env
- [x] src/fetch.py: players→matches→telemetry URL→gzip 해제 (data/*.telemetry.json)
- [x] src/parse.py: LogPlayerPosition·LogPlayerAttack·LogPlayerKillV2 → 플레이어별 시계열
- [x] src/detect.py: ①이동속도 상한 초과 ②피해 이벤트·공격 프록시 z-score ③킬 간격 이상 — signals.json
- [x] src/report.py: 신호별 근거 이벤트(타임스탬프·좌표·수치) 인용한 review-queue.md 생성
- [ ] (선택 발표물) 실행 결과 스크린샷 → README; PLANNING §6 완료 조건 아님
- 키 없는 검증 입력은 `tests/fixtures/TESTMATCH.telemetry.json`이다. [공식 api-assets](https://github.com/pubg/api-assets)는 아트 리소스·데이터 사전 용도로 참고한다.
- [x] 로컬 공개 후보 준비: 실명·공개와 무관한 문맥 제거, README 표본·API 제한 고지, push 게이트. 원격 반영 완료를 뜻하지 않는다
- [x] API 입력 하드닝: v2 `--api-call-limit` 3~60 강제, 빈 `.env` 키의 환경변수 폴백·사전 종료
- [x] 공개 회귀 하드닝: 53-event TESTMATCH fixture·parse→detect→report 정확 기대값·18개 테스트·최소 CI
- [x] 결과 해석 하드닝: README에서 v2·v3 legacy 결과와 현행 protocol 3 preflight 중단을 분리
- [x] Bronze EDA 리포트: 588파일, telemetry 134판, 5,053,469개 이벤트 전수 집계와 PUBG 공식 스키마 교차검증
- [x] Silver EDA 리포트: 운영 파일 143개, 134판, player-match 9,237개의 계보, protocol, key 계약과 분석 준비도 교차검증
- [x] Medallion schema 리포트: Bronze 48 event type과 83개 합집합 필드, Silver 데이터셋별 2~22필드,
  Gold 결과별 6~18필드, Manifest root 7필드의 의미와 버전 차이를 단일 HTML로 문서화
- [x] 관계 graph feasibility: protocol 2 Silver observation 93판의 반복 pair 460개, key 경로 93/93,
  lineage DAG를 stdlib 메모리 투영으로 검증하고 graph 테스트 4개와 전체 22개 통과,
  `FEASIBLE_FOR_NEO4J_REVIEW`로 동결하고 MECE 구현 보고서 작성 (`ADR 013`)
- [x] SQL 교차검증: protocol 2 Silver observation 93건을 in-memory SQLite에 투영하고,
  PK, FK, CHECK, window function, 조건부 집계와 재귀 CTE로 Gold 교차검증 13/13 PASS,
  SQL 테스트 4개와 전체 26개 통과 (`ADR 014`)
- [x] 최소 온톨로지 선행 연구: Neo4j 기각, RDFLib와 pySHACL 격리 smoke, RDF와 SHACL Core 및
  PROV-O 기반 file sidecar, competency query, 보안과 재현성 gate를 `DESIGN_READY`로 문서화 (`ADR 015`)
- [x] 최소 온톨로지 구현: RDFLib 7.6.0과 pySHACL 0.40.1, HTTPS namespace IRI와 source, SHACL과 CQ 6개,
  별도 semantic Manifest를 post-run shadow로 구현했다. 실 v3 51,892 triples와 DQ PASS,
  기존 v3 Manifest 불변, API 호출 0회를 확인했다 (`ADR 016`)
- [x] semantic 판정 용어 교정: 반증 명제와 프로젝트 상태를 분리하고 외부 정확도는 `NOT_EVALUATED`,
  identity 검사는 `LIMITED_PASS`, web 발행은 당시 `DEFERRED_PRIVATE_REPO`로 기록했다. 비공개 전제는 2026-09-10 public 확인으로 교정했다
- [x] semantic 재검증: Python 3.12.3에서 51,892 triples, DQ 11/11, CQ 6/6 PASS, SQL audit PASS,
  전체 테스트 31/31 PASS. Python 3.11.15 runtime 차이는 Manifest write-once가 exit 2로 차단
- [x] PySpark 적용 판단: 현재 workload와 단일 머신 실측을 기준으로 미사용 근거 및 재평가 조건을 문서화
- [x] 로컬 공개 경계 정리: 추적 후보에는 기술 정본만 남기고 대상별 전달 자료는 Git 비추적 경로로 격리 (`ADR 017`). 원격 경계 정리는 보류
- [ ] 원격 공개 이력 정리: `PAUSED_BY_USER`, 다음 명시 지시 전 commit, push와 이력 재작성 미실행
- [ ] ontology namespace web 발행: 원격은 public(2026-09-10 확인)이며 web 발행은 보류. 재개 결정 뒤 Pages 설정·URL·content type 별도 검증
- [x] 2026-09-09 현황 점검: 정본과 핵심 코드의 목적·처리 흐름·중단 상태 확인, 합성 회귀 게이트 통과
- [x] 2026-09-09 검증 범위 재점검: 기존 31개 테스트와 SQL audit 13/13 통과, 강제 종료 뒤 호출 예산 누락을 오프라인 재현
- [x] ApiSession 강제 종료 복구: 요청 전 예약·완료 연결과 전역→실행 원장 복구, 4개 강제 종료 지점·예산 차단 회귀 통과
- [x] 2026-09-09 검증 범위 2차 점검: SQL NULL 반례에서 13/13 PASS·리포트 발행을 재현; 실 evaluated 80건의 해당 결측은 0건, 합성 회귀 통과
- [x] SQL 상태 CHECK 보완: 상태 조건 전체 IS TRUE로 부적절한 NULL 거부, 정상 NULL 허용 회귀 통과

## 로컬 배치 고도화 — 2026-09-09 사용자 승인

- [x] 호출 예약 원장·SQL NULL 조건 수정과 회귀
- [x] 공통 파싱·탐지·비식별·리포트 계산 추출
- [x] SQLite 작업 등록·재개·재시도·원자적 결과 저장과 CLI
- [x] 원시 공격·피해 이벤트 SQL 검산과 운영 분석
- [x] 강제 종료·중복·손상 입력·비식별·동결 보존 검증: 공개 43건을 Python 3.10/3.11/3.12에서 통과, 동결 723개 SHA 유지·기존 SQL audit 13/13
- [x] 공개 demo, 1M/10M 및 실 데이터 측정, 운영 절차와 문서 동기화: demo 2작업·3신호·중복 시도 0, 동결 134판 성공, 준비 1회+측정 3회씩 총 20회 결과 해시 일치
- 2026-09-09 코드 측정: 1M/10M run 중앙값 10.52/113.85초, 시도별 기록 VmHWM 최대 86,264/86,428KiB, 증가 0.19%로 목표 20% 이내. 매치당 최대 4만 이벤트 조건이며 프로세스 종료까지의 최대 RSS는 아니다. 상세 환경·입력 byte·한계는 README에 기록.
- 로컬 원자료: `~/.local/state/pubg-telemetry-watch/benchmark-20260909/measurements.json`, 요약 `performance-summary.json`. 코드·생성기·입력·결과 해시와 query plan 포함.
- [x] 2026-09-10 sip: 별도 문맥 냉독, 외부 근거 대조, 검증 독립성과 SSOT 감사. 검사 직후 입력 교체·runtime 변경 demo·CLI 오류 계약을 수정하고 배치 12개/전체 46개를 Python 3.10·3.11·3.12에서 통과.
- [x] 수정 코드로 동결 134판·SQL audit 13/13·723개 SHA 유지, 1M 준비 1회+측정 1회 실행 확인. 이전 0.19%는 2026-09-09 코드의 시도 기록 RSS 비교이며, 당시 EXPLAIN은 설명용 매개변수였음을 [README](README.md#로컬-배치-실행과-sql-검산)에 명시.
- sip 원자료: `~/.local/state/pubg-telemetry-watch/sip-20260910/verification.json`. 코드 `0fa87c86c846a715adaded1ca47b383f4cbd00377b447591a96cb1f54477159f`. 문서 구조 통합은 하지 않고 SSOT 감사로 종료.
- [x] 2026-09-10 factchk: 키·실 데이터 없는 소스 복사본을 새 venv에 설치해 46개 검사·demo 통과. 원격 public·master `e8719d8`·과거 CI 상태 확인, 비공개 운영이라는 문서 전제 교정. commit·push·이력 정리는 기존 보류 유지. 원자료 `~/.local/state/pubg-telemetry-watch/final-audit-20260910/`.
- [x] 2026-09-10 문서 정리·종료: 과거 연구 기록과 최신 배치 검증의 참조를 분리하고 로컬 완료·원격 미반영 상태, 키 없는 합성 입력, 측정 범위를 교정했다. 코드·동결 데이터 변경 없이 종료 기록을 남겼다.
- 다음 재개 지점: 현재 미커밋 변경을 보존한 채 반영 후보와 문서 일치를 검토한다. 원격 반영·이력 정리는 명시적 재개 지시 범위에서만 수행하고, 실제 전달 commit의 새 설치·demo·CI를 확인한다. 새 기능과 API 수집은 시작하지 않는다.

## 확장 로드맵 (2026-09-01 기획 추가 — 순서 준수)

목표·표본·지표·성공/중단 조건의 정본은 [`PLANNING.md` §8](PLANNING.md#8-버전별-실험-계약-목표방법론-정본)이다.

- [x] **v1 — 파이프라인 성립성**: 공개 3판 구 protocol은 관련 51,995개·REVIEW 7건;
  `rules-event-context-2` 재처리는 groggy 포함 52,241개·REVIEW 0건·DQ PASS
- [x] **v2 — 상위권 기준선 적합성**: top10 최근 고유 38판, 기술 관측 30건/9명, 과거 평가 분모 미확보, 임계값 유지 (`docs/adr/001-elite-r2-baseline.md`)
- [x] **v1/v2/v3 실험 계약 SSOT**: `PLANNING.md` §8 및 구조 결정 [`ADR 002`](docs/adr/002-version-experiment-contract.md)
- [x] **v3 고정 protocol 2**: top100 내부 holdout, 최근 5개, prior match 제외, 공유 match 단일 귀속, 상태·분모 결정표
- [x] **통계 방법론 팩트체크**: 정확 이항 경계·Wilson·player-cluster bootstrap·holdout 보호 근거 문서화
- [x] **Medallion 구현**: Bronze 원문 보존 → Silver 검증·정규화(v3 비식별) → Gold 결과, manifest·DQ 발행 게이트
- [x] **v3 실행기 구현**: snapshot cache, 세션 호출 원장, 7초 간격, 60회 hard cap, 중단 재개, 오프라인 평가
- [x] **v3 수집 preflight**: source 92·owner 90, 순위 1~10은 2명·4건으로 회고 FAIL; 후속 collect는 API 세션 전 차단 (`ADR 008`)
- [x] **현재 데이터 이관**: v1/v2 원본을 삭제하지 않고 계층 경로로 연결, checksum·lineage·DQ 결과 생성
- [x] **구현 검증**: 단위·오프라인 통합 14건 + AGENTS §2 회귀 게이트 + v1/v2/v3 manifest 재검산 통과
- [x] **sip MECE 검증**: 냉독·외부 팩트체크·독립성/SSOT 감사, Windows UTF-8 회귀 수정과 게이트 통과
- [x] **sip 교정 승인 반영**: v2 분모 미확보, R2 프록시·평가 풀 11, v3 내부 holdout 100명·prior match 제외; 10/10·TESTMATCH·v1/v2 DQ 통과 (`ADR 005`, `ADR 006`)
- [x] **v3 실 API 실험**: 425/425 처리·DQ PASS·1차 REVIEW 0/24·2차 0/80; 사전 59명·150건 미달로 `INTERMEDIATE` 동결 (`ADR 007`)
- [x] **사람 판독**: v1 REVIEW 7건을 Bronze 원문과 교차대조. R2 2건은 피해량 0 DBNO 계수,
  R3 5건은 DBNO 정산 문맥을 확인했고 자동 판정은 유지 (`docs/adr/009-v1-human-review.md`)
- [x] **사람 판독 개선 protocol**: R2 양수 피해·attackId 연결, R3 groggy 행동 시각, AI 유형 층화를
  `rules-event-context-2`로 구현하고 기존 3판을 7→0건으로 재처리 (`ADR 010`)
- [x] **protocol 계보 보존**: v2 legacy와 완료된 v3 protocol 2는 재작성하지 않고, 새 v3 실행을
  `v3-r2-top100-3`으로 분리; protocol 2 artifact 631개 checksum PASS
- [x] **v3 protocol 3 독립 snapshot**: prior 466개·교집합 0, API 12회; source 31·owner 30·후보 119로
  preflight 네 조건 FAIL, collect 미실행 (`ADR 011`)
- [x] **독립 참조 first-nail 계약**: 서로 다른 player-match 양성 20·음성 20, 출처 눈가림,
  동결 룰 혼동행렬과 민감도·특이도 양측 95% 정확 이항구간을 PLANNING §8.5에 고정
- [x] **라벨 원천 감사와 중단**: 기존 player 응답 200행(고유 105명)·공식 API/공지·공개 연구를
  대조했으나 엄격 적격 양성 0/20·음성 0/20. 일반화 계획 폐기, 추가 API 0회·검증기 미구현 (`ADR 012`)

## 이번 구현 순서

1. 정본·방법론·ADR에 Why/What/How와 외부 근거를 먼저 고정한다.
2. 공통 atomic/write-once/checksum 경로를 추가하고 기존 v1 흐름을 Medallion에 연결한다.
3. v1/v2 legacy 이관기와 DQ manifest를 구현해 현재 데이터를 실제 계층화한다.
4. v3 `init → collect → evaluate`를 구현하고 네트워크 없는 합성 테스트로 split·통계·재개를 검증한다.
5. AGENTS §2 합성 회귀 게이트와 전체 테스트를 통과한 뒤 README·상태·LOG를 동기화한다.

## 승인 질문 — 2026-09-01 sip 감사 (사용자 `진행`으로 권고안 승인·반영)

1. [x] v2는 후보 기록 0건·후보율 산출 불가로 정정하고 다음 실행부터 배타 분모를 기록한다.
2. [x] v3는 내부 holdout 재현성, 새 시즌·지역·시점만 외부 검증으로 구분한다.
3. [x] 40/60을 폐기하고 top100 전원을 내부 holdout으로 사용한다.
4. [x] 탐지 호환 경계 8은 유지하되 후보율 평가 최소 풀은 11명으로 둔다.
5. [x] 현 R2를 `damage_events/attacks` 프록시로 명시하고 새 지표는 별도 승인 전 구현하지 않는다.

## 승인 질문 — 2026-09-02 사람 판독 (사용자 승인·반영)

1. [x] **R2 이벤트 유효성**: 분자를 `damage > 0`이면서 대상의 `LogPlayerAttack.attackId`와 연결된
   이벤트로 제한한다. 진단 재계산에서 기존 두 건의 z는 3.45·3.62에서 0.65·-0.32가 됐다.
2. [x] **R3 시간 의미**: DBNO가 있으면 대상이 만든 `LogPlayerMakeGroggy` 시각, 직접 종료면
   `LogPlayerKillV2` 시각을 사용한다. 기존 다섯 건은 이 행동 시각 기준 모두 12초 창을 벗어났다.
3. [x] **AI 층화**: 이벤트를 버리지 않고 피해 대상의 원시 `type=user_ai` 여부를 별도 층으로
   보고한다. 기존 R3 다섯 건 중 세 건이 이 층이었다.

## 승인 질문 — 2026-09-02 v3 protocol 3 독립성 (사용자 `진행`으로 승인·반영)

- 무호출 재현에서 현 정책은 protocol 2 후보 425/425를 다시 선택했고, 평가된 80건만 제외해도
  345건이 중복됐다. 이전 후보 425건 전체를 제외하면 같은 snapshot의 후보는 0건이었다.
- [x] **권고안**: protocol 3의 prior exposure를 v1/v2와 모든 이전 v3 동결 후보로 확장하고,
  이전 v3 후보와 교집합 0을 발행 게이트에 추가한다. 승인 시 현 시점 새 snapshot의 `init`
  12회까지만 실행하며 preflight FAIL이면 `collect` 없이 중단한다.
- 실행 결과: 12/12회 HTTP 200, 최소 간격 7.000127초, source 31·owner 30·후보 119로 FAIL;
  `collect`는 호출하지 않았다.

## 2026-09-02 독립 참조 first-nail — 사용자 지시로 실행·중단

- [x] 참조 적격성·40건 표본·눈가림·혼동행렬·정확 이항구간 계약을 API 호출 전에 동결했다.
- [x] 캐시와 공식·연구 원천을 감사했다. player-match에 직접 연결되는 독립 참조는 0건이다.
- [x] 양성 0/20·음성 0/20로 중단 조건을 발동했다. 추가 API 호출·평가 코드 구현·분모 없는 통계 산출을 하지 않았다.
- [ ] 재개 조건: 서로 다른 player·match의 적격 참조 양성 20건과 음성 20건을 외부에서 제공하고
  별도 실행 승인을 받는다. 충족 전에는 활성 작업이 아니다.

## 2026-10-27 계획 문서화 — 사용자 요청

- [x] 합의된 후속 계획을 로컬 비추적 참고서로 저장했다. 기존 구현과 예정 작업, 과거 실측과 신규 baseline을 구분하고 M0~M8의 선행 조건·완료 증거를 정리했다.
- [x] 합성 오프라인 실행·동결 보존·SQLite·CLI 검토 상태, SQL 전수 문서화·도식·단일 VM 재현·반출 계획을 기록했다. 기술 정본·실행 코드·원 연구 계약은 변경하지 않았다.
- [x] 문서 내부 파일 링크 21개·마일스톤 9개·Git ignore를 확인했고, TESTMATCH parse→detect→report 회귀 게이트와 diff 공백 검사를 통과했다. 전체 테스트·신규 benchmark·도식 export 렌더링은 수행하지 않았다.
- [x] 위 항목은 계획 저장 당시의 기록이다. 후속 구현·측정·CI 확장의 실제 결과와 클라우드 blocker는 아래 실행 항목에 기록했다. 신규 API 수집과 동결 실험 재개는 범위 밖이다.

## 2026-10-27 구현 실행 — 사용자 승인

- [x] M0: `feat/gcp-staging-architecture-sql` 브랜치 생성, 기존 변경 상태·소스 65개와 data/reports 837개 SHA 보존. 기존 전체 46개 검사·TESTMATCH·합성 demo 통과. 원자료 `private/runs/20261027/before.json`, 소스 보존본 `before-source.tar.gz`.
- [x] M1: AST·SQL statement·helper·내장 child script·문서 질의 목록과 D01~D12 draw.io/SVG/PDF 초안. SQL 계약·정합 검사 도구 추가.
- [x] M2: 커밋 후 지연·전체 프로세스 RSS 계측, 1M/10M 준비 1회+측정 3회 및 총 1M의 100k/200k 매치 민감도, 총 16회 baseline 동결. 10M run 121.69~179.72초 변동은 그대로 보존하고 작은 개선의 인과 해석을 보류한다.
- [x] M3/M4: 6개 review CLI·schema v2·상태/메모 append-only 이력·원자적 case 생성. 검토/배치 21개 검사와 최종 합성 시연: 종료 재개, 중복·메모 보존, backup 복원·report byte 동일 확인.
- [x] M5 로컬: baseline 16회와 review 16회의 입력·actor 대응 결과 일치. 10M baseline 시간 변동으로 개선/비용의 인과 해석은 INCONCLUSIVE_VARIATION, 추가 최적화 없음. 원자료를 보존하고 통제 환경 재측정은 미실행 대안으로만 기록했다.
- [x] M6 로컬: Python 3.10.20/3.11.15/3.12.3 각각 62개 tests·demo·SQL coverage, 자식까지 namespace 격리 PASS. SQL 계약 20개의 배타적 소유권·87개 실행 지점·117개 고유 정적 텍스트를 관리하고 draw.io/SVG/PDF 15개 도식·보안 경계·재현 절차를 작성했다. 원격 CI 성공을 뜻하지 않는다.
- [x] 로컬 반출·복원: `private/runs/20261027/operations-evidence.tar.gz`의 964개 파일 SHA 일치, 새 경로에서 SQLite integrity/FK·전체 dump·이력 8행·report byte 동일. source/runtime manifest·입력·32회 측정·query plan·로그 보존. cloud/독립 외부 백업 검증으로 대체하지 않는다.
- [x] 보존·문서 gate: 동결 837개 SHA, PLANNING §5·DESIGN §4·기존 LOG prefix 보존, 문서 로컬 링크 333개·diff 검사 PASS. 최종 근거는 [운영 검증 결과](docs/operations-validation.md)와 `private/runs/20261027/bundle-verification.json`이다.
- [ ] M6 원격 CI: 기존 원격 반영 보류가 해소되지 않아 commit/push/원격 실행은 미실행.
- [ ] M7/M8 BLOCKED: 현재 크레딧·평가판 상태·정확한 만료 시각 미확인, Compute API 비활성. API 활성화·VM 생성은 중단한다. 상세와 미실행 대안은 `private/runs/20261027/blockers.md`. 확인할 정보: 잔액·만료 UTC·유료 전환 여부.
- blocker는 우회하지 않고 해당 단계만 멈춘다. 대안은 문서에만 기록한다. 원격 반영·공개 이력 정리 보류는 유지한다.
- [x] 설치·오프라인 검증: 새 Python 3.10.20/3.12.3 및 기존 3.11.15에서 각각 57개 검사·demo·SQL coverage PASS. `unshare`로 다른 net namespace와 자식 상속·외부 route 차단을 확인했다. sysfs를 잘못 사용한 사전 검사 실패는 동일 격리 안의 socket 인터페이스 확인으로 검사 코드를 교정했다. 원격 CI 실행을 뜻하지 않는다.
- [x] 최종 추가 gate: SQL 소유권·도식 active content/경로·assert 비활성 거부·위쪽 화살표 회귀를 포함해 62개로 확장, 세 runtime에서 동일 격리로 모두 PASS. Google SVG 색상 CSS의 제한된 문법을 검증하며 원본 아이콘 SHA를 유지했다.
- [x] 전체 리팩터링의 범위·의존성 방향·단계·보안·채택 gate를 [후속 계획](docs/maintenance/refactoring-plan.md)으로 문서화했다 (`ADR 021`).
- [x] 후속 전체 리팩터링 실행: 사용자 후속 승인으로 계산·application·adapter·CLI와 연구/audit 경로를 분리했다. 기존 운영 기능 완료 기록과 구분하며 최신 채택 증거는 아래 R0~R6을 따른다.

## 2026-10-27 클라우드 종료 별도 작업 — 사용자 승인

- [x] 지정 GCP 프로젝트 전체(기존 리소스 포함)를 2026-11-01 23:00 KST까지 정리하는 계약을 별도 작성했다. 20:00 정리 시작, 전날 23:00까지 증빙 반출·복원 검증 계획이며 실제 평가판 만료 확인과는 구분한다.
- [x] 프로젝트 ACTIVE·결제 연결·활성 API 33개·버킷 2개를 읽기 전용으로 확인하고 응답을 보존했다. 별도 계획·원자료는 `private/cloud-retirement/20261101/PLAN.md`와 `evidence/`, 결정은 ADR 020이다.
- [x] 로컬 증거의 프로젝트 범위·신선도·checksum·경로 점검 코드와 7개 테스트, TESTMATCH 회귀·Git ignore·diff 공백 검사를 통과했다. 삭제 executor와 예약 기능은 미구현이다.
- [ ] BLOCKED: Cloud Asset API 비활성으로 전수 자원 목록 미확보; WSL systemd offline으로 예약 실행기 미확보; 기존 두 버킷 7일 soft delete 보존; lien 조회 90초 timeout. 클라우드 시연 촬영·최종 backup/복원·결제 약정 및 삭제 권한도 미확인이다.
- [ ] 재개 조건/질문: 전수 목록 조회를 위한 API 활성화, 대상 밖의 상시 예약 실행 환경, 버킷 보존 정책의 처리 방안, lien 조회 원인 해결이 필요하다. 대안은 별도 계획에만 기록했고 우회·정책 변경·삭제·자동 예약은 하지 않았다. 현재 상태는 `preflight-result.json`의 BLOCKED / scheduled=false다.

## 2026-10-27 클라우드 종료 문서 통합 — 별도 작업

- [x] [통합 참조](private/cloud-retirement/20261101/README.md)에 최신 승인 범위·기한, 조회·시험 원자료, blocker·미실행 대안, 보안·증빙 설계, 재개 순서를 연결했다. 이전 마일스톤의 신규 자원만 정리 범위는 해당 지정 프로젝트의 기존 자원까지 포함하는 후속 승인으로 대체됨을 표시했다.
- [x] 로컬 파일 링크 50개·원본 증거 14개 checksum 보존·Git ignore·diff 검사·TESTMATCH 회귀 게이트 통과. 결과는 `private/cloud-retirement/20261101/documentation-check.json`에 저장했다. 클라우드 재조회·변경·삭제 예약은 하지 않았고 BLOCKED 상태와 외부 백업 미검증을 유지한다.

- [x] main이 다음 필수 PLAN 읽기에서 발견하도록 문서 최상단에 후속 지시·통합 참조·BLOCKED 상태를 표시했다.
- [x] main 인수 확인 (2026-10-27): 통합 참조·실행 계약·ADR 020·preflight-result를 읽었다. 지정 프로젝트 전체(기존 자원 포함), 2026-11-01 23:00 KST 기한과 B01~B06 BLOCKED·scheduled=false를 확인했다. 다음 조치: 본 작업의 이전 “새 자원만” 서술을 후속 계약 참조로 정정하고 로컬 증빙만 완성한다. 클라우드 변경·삭제·예약·우회는 실행하지 않는다.


## 2026-10-27 전체 리팩터링 실행 — 사용자 승인

- [x] R0: 시작 source 109개·frozen 837개 hash, dirty 상태, 기존 62개 오프라인 gate와 별도 브랜치 확보.
- [x] R1~R4: PUBG/domain 계산, 명령·조회 application, Files/Clock/HTTP/SQLite/RDF adapter, CLI composition과 호환 진입점 구현. 기존 schema·룰·어휘·원자성 유지.
- [x] R5: 실제 경계 장애 주입, 계층/cycle/fingerprint·보안 검사, MECE SQL 20계약·81 실행 지점·22 helper·117 정적 text, draw.io/SVG/PDF 20개와 source 문서 연결.
- [x] R6: 3 runtime 각각 67 tests·demo·namespace·SQL coverage; 새 기준선 전후 32회·actor parity; 이전 DB/report/이력 호환·backup 복원·동결 checksum 확인. 새 최적화는 없음.
- [x] blocker와 미실행 대안: GCP 사전조건·종료/예약·장기 관측·원격 CI를 로컬 완료와 분리해 기록; 우회 실행 없음.
- [ ] GCP M7/M8·원격 CI·commit/push: 기존 선행 조건 및 보류 범위가 해소되기 전까지 미실행.

## 2026-10-27 세션 종료 — 사용자 요청

- [x] [HANDOFF](private/refactoring/20261027/HANDOFF.md)에 읽기 순서, 현재 브랜치·HEAD·dirty 상태, 구현 위치, 검증 수치·bundle checksum, 보존 계약·blocker·미실행 대안·재개 절차를 저장했다.
- [x] 로컬 구현 완료와 GCP/원격 CI/독립 외부 복원 미검증을 구분했다. 기존 archive는 변경하지 않으며 PLAN/LOG 종료 기록의 차이는 `private/refactoring/20261027/handoff-check.json`에 남긴다.
- [x] 사용자 지시로 현재 세션을 종료한다. 다음 지시 전 구현·수집·배포·commit/push·cloud 변경/삭제/예약을 진행하지 않는다.
- [x] 후속 요청의 중요한 /tmp 정보만 분류했다. 기존 보존본과 1,720개 파일 참조의 SHA를 대조하고 실패 로그·최종 도식 확인 이미지·측정 순서 7개(272,141 bytes)를 private에 추가 보존했다. 가상환경은 버전/실행 파일 근거와 재구성 조건을 기록했으며 기존 archive·실행 코드는 변경하지 않았다.

## 2026-10-28 GCP 인증·Asset 조회 재개

- [x] 기본 WSL 인증 설정과 기존 Windows 설정의 차이, 사용자 명령의 프로젝트 ID 마지막 문자 누락을 확인했다. 새 로그인·인증 파일 복사·계정 전환은 하지 않았다.
- [x] 사용자 Asset API 활성화 시도에 따라 정확한 프로젝트 ID·번호·ACTIVE 상태를 확인한 후 해당 API를 활성화했다. 활성 서비스 34개·Asset 검색 메타데이터 83건을 확인하고 로컬 비추적 후속 증거로 보존했다.
- [ ] API 비활성 원인은 해소됐으나 서비스별 실시간 전수 대조, B02~B06, GCP 재현의 잔액·만료·Compute 선행 조건은 미완료다. 삭제·예약·보존 정책 변경·원격 반영·commit/push 보류를 유지한다.

## 2026-10-28 GCP DB 선택·계정 상태 사실 조사

- [x] 로컬 계획·ADR·runbook·실행 composition과 상위 작업 폴더의 관련 문서를 대조했다. 현재 확인한 PUBG 계획은 SQLite 유지/PostgreSQL 조건부 보류이며, 별도의 PostgreSQL 확정 마이그레이션 문서는 찾지 못했다. 광역 검색 timeout·누락 경로로 인한 조사 한계도 기록했다.
- [x] 사용자 제공 Free trial·잔여 크레딧·4일 표시값을 private 사실 기록에 보존했다. 직접 콘솔 검증 결과와 구분하며 이전의 사용자 미응답 상태를 갱신한다.
- [ ] 질문: PostgreSQL 확정 지시의 별도 문서 또는 원대화는 어디이며, 현재 SQLite 유지 기록을 대체하는 범위는 무엇인가? 차이가 해소되기 전 DB 선택을 임의로 확정해 GCP 배포하지 않는다.
- [ ] 정확한 평가판 만료 시각은 아직 미확인이다. 계정 정보 수신이 Compute 권한·할당량·외부 복원·자동 종료 등 다른 선행 조건의 완료를 뜻하지 않는다.

## 2026-10-28 체크포인트·스킬 설정·아키텍처 검토

- [x] 종료 인계 요청과 후속 resume를 반영해 기존 증거·GCP/DB 질문·평가판 사용자 제공값·중요 임시자료 경로를 최신 HANDOFF로 연결했다. 변경 전 파일 hash와 dirty 상태를 별도 checkpoint-before.json에 보존했다.
- [x] `setup-matt-pocock-skills`: 로컬 Markdown `.scratch/`, 기본 triage 5상태와 전체 초안을 사용자가 확인했다. AGENTS 연결·Git ignore·설정 문서 3개·ADR 023을 적용했다. GitHub 이슈/라벨·commit/push는 실행하지 않았다.
- [x] `improve-codebase-architecture`: 최근 배치·검토 module을 읽기 전용 에이전트와 대조하고 HTML 후보 2개·변경 전후 도식·메모리 DB 재현을 보존했다. browser 열기 exit 0에 Broken pipe 오류가 동반되어 실제 표시는 미확인이다.
- [x] 사용자 선택: 01 조회 snapshot 수명 정리. 기존 CLI는 호출마다 연결을 닫으며, 재현된 실패는 동일 Operations 인스턴스의 연속 조회·예외 뒤 재사용 범위다.
- [x] `grilling` Q1: 사용자는 이미 열린 transaction 재사용·소유자만 종료에 동의했다. 직접 연 조회 snapshot만 성공·오류 시 종료하며 report의 복합 조회와 호출자의 쓰기 transaction을 보존한다.
- [x] [구현 범위 초안](.scratch/review-snapshot-lifetime/spec.md)의 내용을 후속 티켓의 완료 기준으로 구체화하고 2026-10-29 사용자에게 범위·분할안을 확인받았다. 원래 명세 파일은 당시 상태로 보존한다.
- [x] 발행된 조회 snapshot 티켓은 후속 implement 지시로 구현에 착수했다. 최신 진행·미완료 검증은 2026-10-29 인계 항목을 따른다.

## 2026-10-28 조회 snapshot 티켓화

- [x] `to-tickets`로 현재 합의와 로컬 tracker·triage·ADR을 대조했다. 구현·CLI 연결·회귀·설계/SQL/도식 갱신을 포함하는 완결 티켓 1개와 완료 기준 8개를 초안으로 작성했다.
- [x] 별도 prefactor·문서 전용 티켓은 만들지 않는다. 검토 조회와 상태/보고서 조회를 2개로 나누는 대안은 미채택으로 기록했다. 원래 명세·애플리케이션 코드·기존 checkpoint를 보존했고 TESTMATCH를 통과했다.
- [x] 2026-10-29 사용자 확인: 완결 티켓 1개, 선행 티켓 없음, 완료 기준 8개를 확정했다.
- [x] 확인된 내용을 로컬 tracker의 issue 파일 하나로 발행했다. `ready-for-agent`는 실행 가능 상태이며 구현 완료가 아니다.

## 2026-10-29 승인된 로컬 티켓 발행

- [x] 승인된 본문을 [티켓 01](.scratch/review-snapshot-lifetime/issues/01-owned-read-snapshots.md)로 저장했다. 부모 명세·제안·기존 checkpoint는 변경하지 않았다.
- [x] 발행 본문 일치·단일 파일·선행 관계·완료 기준·Git ignore·원본 보존·TESTMATCH·diff 검사 PASS. 최신 발행 근거는 [tickets-published.json](private/planning/2026-10-28-session/tickets-published.json)에 보존했다. 구현은 미착수다.


## 2026-10-29 조회 snapshot 구현·인계 — 사용자 implement / handoff

- [x] 시작 파일 hash·내용 복사와 이전 코드 합성 DB를 보존한 뒤 조회 소유권을 port/adapter/application에 구현하고 CLI의 직접 BEGIN을 제거했다.
- [x] review 누수·status 혼합·report 중첩 실패를 TDD로 재현·수정했다. 새 실제 SQLite 회귀 6개와 TESTMATCH PASS.
- [x] 이전 DB 조회·메모/완료 상태·보고서 4개 SHA·backup/복원·새 코드 note, BATCH_CODE_CHANGED와 동결 837 SHA를 확인했다.
- [x] DESIGN·ADR 024·SQL 20계약/88 실행 지점·12개 조회 계획·D17 및 20쪽 PDF·부분 검증 문서를 갱신했다.
- [x] 사용자 handoff 요청으로 OS 임시 문서와 private 보존본·증거 색인·checkpoint를 보존했다. 기존 source·archive·과거 checkpoint를 덮어쓰지 않는다.
- [x] 사용자 implement 재개 후 세 runtime의 전체 tests/demo/namespace 격리와 기존 장애 회귀를 확인했다. 각각 73개 PASS이며 세부 결과는 아래 재개 항목을 따른다.
- [x] 타입 검사 처리 결정: 사용자 지시로 이번 티켓은 NOT RUN으로 명시하고 별도 도입 작업으로 분리했다. 타입 검사 PASS나 도구 설치 완료를 뜻하지 않는다.
- [x] 정식 code-review 비교 기준 결정: 사용자 승인으로 보존 before-source와 고정 after snapshot을 비교했다. 두 축 리뷰와 후속 발견 해소는 아래 정식 리뷰 항목을 따른다.
- [ ] GCP·원격 CI·commit/push는 기존 보류 유지. 로컬 티켓 완료는 외부 반영 완료가 아니다.

## 2026-10-29 ask-matt 개발 흐름 상담

- [x] 정본·현재 티켓·설치 스킬·기존 offline_check/CI를 대조하고, 남은 검증 완료→환경 회고→승인된 티켓 실행의 제안을 [로컬 메모](private/planning/2026-10-29-portfolio-loop.md)에 저장했다. 실행 정책 변경이나 새 구현 승인으로 해석하지 않는다.
- [ ] 고정 snapshot 리뷰와 현 티켓의 타입 검사 NOT RUN 분리를 적용했다. 타입 검사 환경은 아래 별도 도입 작업으로 진행했다. 기존 검사기의 결과 기록은 2026-10-30 resume에서 완료했고, 재개 자동화는 아직 실행하지 않았다.
- [x] 세션 기록용 TESTMATCH 1개와 namespace·자식 격리를 확인했다. 최초 샌드박스의 인터페이스 조회 권한 오류 뒤 승인된 격리 재실행에서 PASS했으며, 현재 티켓의 세 runtime 전체 회귀·최종 리뷰 완료를 뜻하지 않는다. 원격/cloud·commit/push 보류는 유지한다.
- [x] 후속 ask-matt 상담: 조회 snapshot·타입 도입의 로컬 완료와 실제 검사기를 확인했다. 다음 순서는 같은 세션의 `/retro`로 반복 수작업을 좁힌 뒤, 기존 mypy/offline_check의 실행 결과·소스/설정/환경 식별·로그 위치를 자동 기록하는 완결 작업 1개를 구체화하는 것으로 제안한다. 효과는 개입 횟수·재개 시간·기록 누락으로 측정하며 아직 미측정이다. 회고 실행·새 티켓 발행·자동화 구현 승인을 뜻하지 않는다.

## 2026-10-29 조회 snapshot 검증 재개 — 사용자 implement

- [x] 인계 source 지문·198개 파일 상태와 세 runtime을 확인했다. 직전 상담의 PLAN/LOG 추가 및 기존 삭제 표식 외에 예상하지 못한 변경은 없었다.
- [x] 최초 전체 실행에서 Python 3.10 테스트의 authorizer 복구 오류 4건을 재현했다. SQLITE_OK callback으로 세 곳을 수정하고 DESIGN의 검증 계약을 갱신했다. 운영 코드·SQL·의존성은 유지했다.
- [x] 수정 후 3.10 조회 회귀 6개, Python 3.10.20/3.11.15/3.12.3 각각 전체 73개·demo·SQL inventory·namespace/자식 격리 PASS. 실패·최종 로그를 분리 보존했고 동결 837 SHA를 재확인했다.
- [x] 티켓의 동작 완료 기준 8개를 근거와 연결했다. 재개 전 기록을 덮어쓰지 않고 새 실행 폴더에 결과·소스·리뷰 비교 자료를 준비했다.
- [x] 사용자 승인으로 보존 before-source와 현재 고정 snapshot을 정식 리뷰 기준으로 사용했다. 이번 티켓의 타입 검사는 NOT RUN으로 명시해 별도 도입 작업으로 분리했다.
- [ ] commit/push·GCP·원격 CI 보류 유지. 이번 재개는 자동화 도구 신설이나 다른 아키텍처 후보의 구현 승인이 아니다.

## 2026-10-29 조회 snapshot 정식 리뷰 — 사용자 승인

- [x] 고정 before 194개·after 198개 파일과 작업 트리의 hash, 변경 24개·비어 있지 않은 diff를 확인하고 Standards/Spec을 독립 리뷰했다. 원 스킬의 Git ref 방식 대신 사용자 지정 snapshot을 사용했다.
- [x] Spec 발견 0건. Standards의 PDF 전체 페이지 시각 확인 누락 P3 1건은 같은 PDF 20쪽 렌더·페이지별 육안 확인·근거 기록·문서 보완 뒤 독립 리뷰어가 해소를 확인했다. 남은 Standards 발견과 코드 냄새 후보는 0건이다.
- [x] 코드·테스트·SQL·PDF 원본을 변경하지 않고 이전 세 환경의 73개 동작 검증과 정식 리뷰를 연결했다. 티켓의 동작 기준 8개·정식 리뷰를 로컬 완료로 표시하고 외부 반영 보류에 따라 ready-for-human으로 이동했다.
- [x] 사용자 지시대로 이번 티켓 타입 검사는 NOT RUN으로 기록했다. [별도 도입 티켓](.scratch/typecheck-setup/issues/01-configured-typecheck.md)에 도구·버전·초기 범위·실행 명령·검증 기준의 제안과 읽기 전용 조사 결과를 남겼다.
- [x] 사용자는 “리뷰 후 별도 작업으로 설정 진행”을 확인했다. 아래 별도 도입 결과와 구분하며 조회 snapshot 티켓의 타입 검사 NOT RUN 기록은 보존한다.
- [ ] commit/push·원격 CI·cloud 보류 유지. 원 snapshot·인계·과거 로그·archive는 덮어쓰지 않는다.

## 2026-10-29 타입 검사 별도 도입 — 사용자 설정 진행

- [x] [별도 티켓](.scratch/typecheck-setup/issues/01-configured-typecheck.md)에서 개발용 `typecheck` extra의 mypy 2.4.1과 Python 3.10 대상·4개 파일·검사 옵션을 `pyproject.toml`에 고정했다. 실행 의존성·기존 세 환경과 운영 코드·테스트·SQL·offline_check는 보존했다.
- [x] README에 동일 설치/실행 명령과 Any·import 범위의 한계를 기록하고 DESIGN 검증 표와 CI를 연결했다. SQL inventory 변경은 README 예제의 줄 번호 갱신뿐이며 88/22/121/245개 수치는 같다.
- [x] 새 3.10/3.12 환경에서 각각 실제 4개 파일 PASS와 잘못된 port 호출·주석 없는 함수의 잘못된 타입 대입 오류 2건(exit 1)을 확인했다. 최초 음성 검사 명령의 설정 충돌(exit 2)은 실패 원자료로 구분 보존했다.
- [x] 새 3.10 개발 환경에서 기존 전체 73개·TESTMATCH·demo·SQL inventory·namespace/자식 격리 PASS. [원자료](private/typecheck/20261029T050535263672Z/README.md)에 버전·설정 hash·명령·결과를 연결한다. 기존 조회 snapshot 타입 검사 NOT RUN은 변경하지 않는다.
- [x] 도입 전후 고정 snapshot(각 194개 파일·변경 8개)의 독립 Standards/Spec 리뷰는 각각 발견 0건이다. [정식 리뷰](private/typecheck/20261029T050535263672Z/review.md)를 보존하고 로컬 티켓을 완료·ready-for-human으로 이동했다. 외부 반영 보류를 해제하지 않는다.
- [ ] commit/push·원격 CI·cloud 보류 유지. 전체 코드의 엄격한 타입 전환과 작업 재개 자동화는 수행 범위 밖이다.

- [x] 2026-10-29 retro: 현재 세션의 최초/최종 matrix·리뷰 누락·타입 검사 실패와 기존 검사기를 대조했다. [회고](private/planning/2026-10-29-retro.md)에 검증 조건/결과 기록, 리뷰 확인 범위 검사, 현재 상태 진입점, 명령/출력 재사용의 네 후보를 우선순위순으로 기록했다. 3.10 FAIL→PASS의 운영 지문이 같아 검증 재사용에는 테스트·설정·환경 식별도 필요함을 확인했다.
- [x] 후속 제안: 기존 검사 호출을 재사용하는 실행 조건·단계별 결과 자동 기록 작업 1개를 이후 사용자 `resume`에서 구체화·구현했다. 자동 재개·자동 수정과 문서 재편은 별도 범위다. 회고 자체를 구현·보류 해제 승인으로 해석하지 않았으며 실행 결과는 아래를 따른다.

- [x] 2026-10-30 resume 완료: [기록 티켓](.scratch/validation-recording/issues/01-record-check-results.md)에 따라 기존 `offline_check.py`의 선택형 `--record-dir`로 namespace→기존 범위 mypy→전체 tests→demo→SQL의 조건·명령·단계 상태·종료 코드·시간·로그를 저장한다. 기존 비기록 호출과 운영 runtime 지문·의존성은 보존했다.
- [x] 소스·테스트/fixture·도구·설정·공개 문서 190 SHA와 Python/SQLite/패키지 버전을 기록한다. 기존 결과 경로는 거부하며 실패·중단·미실행·검사 전후 조건 변경은 PASS가 아니다. 자동 재개·자동 수정은 구현하지 않았다.
- [x] 최종 Python 3.10.20/3.12.3 각각 기존 73+신규 9=82개·TESTMATCH·demo·SQL·namespace/자식 격리와 기존 4개 파일 mypy 2.4.1 PASS. 두 실행 모두 전후 조건 불변이고 동결 837 SHA를 보존했다. [근거 색인](private/validation-recording/20261029T144329086767Z/README.md)에 최초/최종 결과를 구분했다.
- [x] 고정 before 194개→최종 195개, 변경 8개를 두 축 정식 리뷰했다. Standards UTF-8 누락 P3와 Spec CI 결과 읽기 권한 P2를 수정하고 재검증·재리뷰해 각각 잔여 0건이다. DESIGN·README·runbook·CI를 연결했고 SQL inventory 변경은 README 예제 줄 번호뿐이다.
- [x] 로컬 티켓 완료·ready-for-human 인계. 이전 조회 snapshot 티켓의 타입 검사 NOT RUN과 원 snapshot·로그는 보존한다. 새 검사기의 나머지 코드까지 정적 타입 검사를 확장했다는 뜻은 아니다.
- [ ] commit/push·원격 CI·cloud 보류 유지. SIGKILL/전원 단절의 RUNNING 기록은 미완료이며, 자동 재개와 HITL 절감 효과 측정은 별도 작업이다.
- [x] 2026-10-30 ask-matt: 완료된 기록 작업과 실제 스킬 지침을 대조했다. 같은 세션에서 `/retro`로 남은 반복 수작업 하나를 좁힌 뒤 `/implement`로 완결하는 경로를 권고한다. 직전 최종 요약이 unittest의 버전별 표시 차이로 실패했으므로 다음 후보는 기존 `result.json`을 읽는 결과 판독·후속 작업 안내 명령이다. 현재 세 티켓은 로컬 완료이며 새 작업 그래프는 없다.
- [x] 다음 후보의 최소 범위: 사람이 읽는 unittest 출력 파싱 없이 기존 구조화 결과로 단계 상태·실패 명령·로그 위치를 요약하고, 손상/누락·미완료·현재 조건 불일치를 성공으로 취급하지 않는다. 자동 재개·자동 수정·검사 생략·보류 해제는 포함하지 않는다. 이번 상담은 회고 실행·새 티켓 발행·구현 승인이 아니다.
- [x] 2026-10-30 retro: 기록 구현 세션의 원자료·기존 검사/CI·리뷰를 대조하고 [회고](private/planning/2026-10-30-recording-retro.md)에 결과 판독, CI 생성/읽기 권한 검사, JSON UTF-8 기계 검사, 현재 상태 포인터, 출력/명령 재사용의 다섯 후보를 순서대로 정리했다. 이전 P2/P3는 해소됐으며 후보는 재발 방지와 수작업 축소를 위한 환경 개선이다. 다음 구현 권고는 위 결과 판독 작업 하나이며, 티켓 발행·구현·문서 재편·보류 해제는 하지 않았다.

- [x] 2026-10-30 implement: [판독 티켓](.scratch/validation-status/issues/01-read-validation-results.md)으로 회고 §1을 구현했다. `tools/validation_status.py`는 기존 결과 JSON의 과거 상태·단계 명령/범위/시간/로그와 현재 파일/환경 일치 여부를 읽기 전용으로 출력한다. schema/성공 일관성·필수 로그를 확인하며 exit 0/1/2로 완료·비성공/불일치·판독 오류를 구분한다. RUNNING의 실제 종료를 단정하지 않는다.
- [x] 기존 조건/hash helper와 실제 CLI/file fixture를 재사용했다. CI 판독 호출·DESIGN·README/runbook·mypy 기존 4개+reader 총 5개 파일을 연결했고 새 의존성·운영 코드·SQL은 없다. SQL inventory는 README 예제 줄 번호만 갱신했다.
- [x] 최종 3.10.20/3.12.3 각각 기존 82+신규 9=91개·TESTMATCH·설정된 5개 파일 mypy 2.4.1·demo·SQL·namespace/자식 격리 PASS. 192개 입력 SHA·환경은 실행 전후 동일하며 최종 판독도 각각 exit 0/current_pass=true, 결과와 로그 byte 보존을 확인했다. [근거 색인](private/validation-status/20261029T163831107740Z/README.md)을 따른다.
- [x] 고정 before 195개→final 197개, 전체 변경 10파일을 두 축 정식 리뷰했다. Spec의 namespace 성공 모순 P2 1건을 실제 CLI RED→GREEN으로 수정하고 두 환경 전체 재검증·독립 재리뷰를 마쳤다. Standards 규약/냄새 0건, Spec 잔여 0건이며 최초 snapshot·결과·리뷰는 보존한다.
- [x] 이전 실제 PASS 기록의 현재 10파일 불일치를 판독해 exit 1을 확인했다. 동결 837 SHA와 운영 지문을 보존했고 로컬 티켓을 완료·ready-for-human으로 인계한다. 기존 조회 snapshot 티켓의 타입 검사 NOT RUN과 과거 기록을 소급 변경하지 않는다.
- [ ] commit/push·원격 CI·cloud 보류 유지. 자동 재개·자동 수정·검사 생략·HITL 절감률 측정 및 회고의 나머지 후보는 이 작업에 포함하지 않는다.

- [x] 2026-10-30 ask-matt 완성 경로: 원래 MVP 완료와 네 로컬 티켓 완료를 확인하고 [후속 경로](private/planning/2026-10-30-completion-path.md)에 최종 전달 후보의 새 환경 인수검증·개발 개입량 측정, 공개 반영/원격 확인의 두 작업을 권고했다. 다음 경로는 to-tickets→implement이며 새 티켓 발행·구현·보류 해제는 하지 않았다.
- [x] 위 두 작업은 후속 사용자 to-tickets 요청으로 아래 로컬 티켓에 발행했다. 기존 commit/push·원격 CI·cloud 보류와 M7/M8·외부 복원·종료 계약은 유지한다. 회고 후보 전체나 자동 재개를 현재 완료 조건으로 추가하지 않는다.

- [x] 2026-10-30 to-tickets: 직전 두 작업 제안을 각각 [01 최종 전달본 인수검증·개입량 측정](.scratch/portfolio-completion/issues/01-acceptance-and-hitl.md), [02 공개 반영·원격 확인](.scratch/portfolio-completion/issues/02-publish-and-verify.md)으로 발행했다. 01은 선행 없음·완료 기준 9개·ready-for-agent, 02는 01 완료와 명시적 공개 보류 해제가 필요하며 완료 기준 7개·needs-info다. 원 제안·기존 완료 티켓은 변경하지 않았다.
- [x] 두 파일의 형식·선행 링크·완료 기준·Git ignore·보존 대상 8개 hash와 TESTMATCH parse→detect→report·namespace/자식 격리를 확인했다. 발행 근거는 `private/planning/2026-10-30-completion-tickets/`에 보존한다. 이 검사는 티켓 본문 검증이며 01의 새 환경 인수검증 수행을 뜻하지 않는다.
- [x] 다음 실행 01은 사용자 implement 요청으로 착수했다. 아래 로컬 인수검증 결과를 따르며 02는 선행 작업과 공개 보류 해제 전 실행하지 않는다.

- [x] 2026-10-30 전달본 인수검증: 로컬 공개 기준 commit `e8719d88ca94b5416db9c0484e9b76899df2f1b2`의 46개 파일과 전달 후보 197개 파일을 고정했다. 새 Python 3.10.20/3.12.3 가상환경에 README의 실행·typecheck extra를 설치하고, 기존 작업 트리·가상환경·실데이터·키가 보이지 않는 Linux user/mount/network namespace에서 검증했다.
- [x] 첫 후보는 두 환경 모두 전체 91개·TESTMATCH·설정된 5개 파일 mypy·demo·SQL·namespace/자식 격리 PASS, 192개 검증 입력과 환경 불변, 같은 새 환경의 판독 exit 0/current_pass=true였다. 최초 격리 설정의 UID 0 때문에 중첩 namespace가 거부된 FAIL과 후속 미실행 단계를 보존했고, 이 격리 오류는 제품 코드 변경 없이 검증 환경에서 수정했다. 아래 전체 리뷰 발견을 반영한 최종 결과와 구분한다.
- [x] 공개 문서의 파일 링크 누락은 없고, 기존 구조 안에서 도식 목록 D01–D20의 끊어진 표를 연결했다. 동일 SHA의 PDF 20쪽과 이전 전 페이지 시각 확인 근거를 대조했다. 원자료는 `private/release-candidate/20261029T174046Z/`이며 이전 실행을 새 설치의 PASS로 재사용하지 않았다.
- [x] 전체 후보 리뷰의 Spec P2(graph/SQL semantic 실패 진단 누락)를 실제 합성 file 경계에서 RED로 재현하고, 원문 없는 단계 진단 갱신·과거 진단 교체·발행 차단·원본 보존을 GREEN으로 확인했다. Standards P3인 benchmark 비교 JSON의 UTF-8 명시 누락도 수정했다. DESIGN의 실패 계약·책임 표·비교 입력 계약을 함께 갱신했다.
- [x] 수정 후 새 두 환경에서 각각 92개 회귀·TESTMATCH·설정된 5개 파일 mypy·demo·SQL·namespace/자식 격리 PASS와 판독 exit 0/current_pass=true를 재확인했다. `revised/`가 최종 코드의 근거이며 이전 FAIL과 첫 후보의 `final/` 기록은 보존한다. 운영 지문은 수정에 따라 `e6b6827420b41449d025edcb32971c53286b8676a3194e9e84927a42a5b2e412`로 바뀌었다. 룰·임계값·의존성·동결 연구 결과는 유지한다.
- [x] 공개 기준판→후보 전체 181개 변경의 독립 리뷰와 수정 재리뷰를 마쳤다. Standards 규약 발견 0건·Spec 0건이며 비차단 판단인 telemetry 경로 탐색 중복 P3 1건은 권고로 남긴다. 기존 개별 티켓 리뷰와 전체 후보 리뷰를 구분하고 최초 리뷰·실패·수정 근거를 보존했다.
- [x] 수정 후 동결 837 SHA와 선행 보존 대상 8개를 확인했다. 후보 197개 파일의 금지 경로·알려진 인증 값·실플레이어 exact token 검사는 노출 발견 0건이다. 최종 후보·전체 diff·checksum·리뷰·실행 근거와 개입량 집계는 [인수 근거](private/release-candidate/20261029T174046Z/README.md)에 연결한다. 검증 입력 192개는 최종 코드와 일치하며 종료 인계의 PLAN/LOG 변경은 별도 hash로 구분한다.
- [x] 01은 로컬 완료·ready-for-human으로 인계한다. 이 구현 구간의 최초 요청 1건, 추가 지시·사용자 수동 명령·중간 확인 요청은 각각 관찰 0건이다. 첫 시각 표본 이전 구간과 세션 밖 개입은 미측정이며 단일 실행에서 보편적 절감률을 주장하지 않는다.
- [ ] 02의 공개 반영·원격 확인은 명시적 보류 해제와 원격 상태 확인이 필요하다. commit/push·원격 CI·cloud 보류 및 과거 조회 snapshot 티켓의 타입 검사 NOT RUN 기록은 유지한다.
