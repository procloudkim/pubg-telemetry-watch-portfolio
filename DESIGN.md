# 설계서 — PUBG Telemetry Watch

> 구현 인수인계용 정본. 기획 의도는 `PLANNING.md`. 현재 구현·검증 상태와 확인된 결함은 `PLAN.md`를 따른다.
> 버전별 목표·표본·검증 지표의 정본은 [`PLANNING.md` §8](PLANNING.md#8-버전별-실험-계약-목표방법론-정본)이며, 이 문서는 그 목표를 실행하는 구현 계약만 소유한다.

## 1. 아키텍처
```
[PUBG API / Telemetry CDN]
          │ 수신 byte write-once
          ▼
data/bronze/{version}/        API JSON·match metadata·telemetry 원문
          │ parse / validate
          ▼
data/silver/{version}/        정규화 parsed match·cohort·관측
          │ detect / aggregate
          ▼
data/gold/{version}/          R1/R2/R3 신호·v2 기준선·v3 통계 결과
          │ DQ PASS
          ├─→ data/manifests/ checksum·건수·lineage·품질 증거
          ├─→ reports/review-queue.md
          └─→ v3 semantic shadow: RDF, SHACL, SPARQL parity
```
기존 `data/*.json`은 검수 호환 경로로 유지하되 정본은 계층 경로다. 과거 해제 JSON은
`legacy_decoded_json`으로 이관하고 삭제하지 않는다. 상세 계약은
[`docs/architecture/medallion-data-pipeline.md`](docs/architecture/medallion-data-pipeline.md)다.

실험용 graph 경로는 완료된 v3 protocol 2의 Silver observation이 채택한 match만 대상으로 한다.
Bronze roster를 기존 cohort `player_key`로 비식별 투영해 관계와 key 연결 및 manifest DAG를
메모리에서 감사하고 집계 보고서만 발행한다. 별도 graph 저장소와 Gold 변경은 하지 않는다.

Neo4j 도입 경로는 기각했다. 완료된 v3 DQ PASS 뒤에는 파일 기반 semantic shadow sidecar가
RDF, 최소 RDFS와 OWL 2, SHACL Core, PROV-O, SPARQL로 관계 의미와 계보를 교차 표현으로 재검산한다.
RDFLib 7.6.0과 pySHACL 0.40.1을 exact pin하고 기존 graph 및 SQL parity와 비식별 검사를 통과한
sidecar만 별도 semantic Manifest로 발행한다. 기존 v3 Gold와 Manifest는 수정하지 않는다.
상태는 `SHADOW_VALIDATED`, `NOT_PRODUCTION_GATE`다. HTTPS IRI와 source는 고정했고 web 발행은 보류 중이다.
2026-09-10 [GitHub 저장소](https://github.com/procloudkim/pubg-telemetry-watch)와 API에서 public(`private=false`)을 확인했다.
당시 `DEFERRED_PRIVATE_REPO` 기록의 비공개 전제는 잘못됐으며, 저장소 공개와 namespace web 발행은 별개다. 근거와 계약은
[`ontology-production-framework.md`](docs/research/ontology-production-framework.md),
[`ADR 015`](docs/adr/015-file-based-ontology-framework.md),
[`ADR 016`](docs/adr/016-v3-semantic-shadow-sidecar.md)을 따른다.

DQ PASS 이후의 관계형 교차검증 경로는 v3 Silver observation, Gold validation과 manifest를
in-memory SQLite에 투영한다. 이 경로는 관계형 제약, window function, 조건부 집계와 재귀 CTE로
동결 결과를 재검산하고 로컬 `reports/sql-audit.md`만 발행한다. 데이터베이스 파일과 새 Gold는
만들지 않으며 운영 저장소로 사용하지 않는다. 별도 로컬 배치 실행 경로는 §12의 영속 SQLite를 사용한다.

스택: Python ≥3.10, direct dependency는 `requests`, `rdflib==7.6.0`, `pyshacl==0.40.1`이다.
파싱, 탐지, 통계, 리포트, DQ와 SQL audit은 stdlib를 사용하고 semantic shadow만 RDFLib와
pySHACL을 사용한다. 실행은 저장소
루트에서 `python -m src.<모듈>`. JSON·JSONL·`.env` 텍스트는 OS 로캘과 무관하게 UTF-8로 읽고 쓴다.

실행 코드의 책임은 §13과 [계층 문서](docs/architecture/clean-architecture.md)를 따른다.
기존 `src.<모듈>` 명령은 호환 진입점이며 실제 계산은 domain, 실행 순서는 application,
외부 자원과 표현은 adapters, 인수·조립·출력은 cli가 소유한다.

## 2. API 세부 (실측 기반 주의사항)
- 인증: `Authorization: Bearer <PUBG_API_KEY>` + `Accept: application/vnd.api+json`. 비어 있지 않은
  `.env`의 `PUBG_API_KEY=` 값을 우선하고, 빈 값이면 비어 있지 않은 프로세스 환경변수로 폴백하며
  둘 다 없으면 요청 전에 종료한다 (`src/common.py`)
- 레이트리밋: 공식 기본값은 10 RPM이며 공식 문서상 `/matches`·telemetry는 제한 대상에서
  제외된다. 이 저장소는 더 엄격한 사용자 계약에 따라 인증 API 전체를 7초 간격·세션 60회 이하로 제한한다
- 플레이어 조회: `/shards/{shard}/players?filter[playerNames]=<닉>` — shard는 `steam` 또는 `kakao`(한국 카카오 계정)
- 닉네임 없이: `/shards/{shard}/samples` — 랜덤 공개 매치 목록 (`--sample`)
- 엘리트 기준선: 현재 시즌은 `/shards/steam/seasons`, 리더보드는 지역 플랫폼
  `/shards/pc-as/leaderboards/{seasonId}/squad-fpp`. leaderboard는 top500을 제공하며 player 상세는
  최대 10 ID씩 조회한다. v2 top10은 1 batch, v3 top100은 10 batch다. v2 `--api-call-limit`은
  초기 3회와 세션 상한을 반영해 3~60만 허용한다
- 텔레메트리 URL은 매치 응답의 `included[type=asset].attributes.URL` — **CDN 다운로드는 키 불요**.
  `requests` 자동 디코딩을 끈 수신 byte를 Bronze에 먼저 저장하고 gzip 매직바이트(`\x1f\x8b`)로
  감지해 parser 입력을 해제한다
- v3는 HTTP 전에 v2 예약(`request_id`, `phase=reserved`)을 fsync하고 완료 뒤 `completed` 행을 추가한다.
  전역 원장이 정본이며 실행별 원장의 누락 v2 행을 재시작 때 보충한다. legacy 행은 재작성 없이 읽는다.
  미완료 예약도 예산 한 건으로 차감하고, 손상 원장은 요청을 차단한다. `network_calls`는 v2가 섞이면
  잠재 호출 상한이며 `completed_requests`·`uncertain_requests`로 확인 여부를 분리한다. 성공 cache는
  호출하지 않는다. 키와 Authorization header는 어떤 산출물에도 기록하지 않는다

## 3. 텔레메트리 이벤트 스키마 (사용하는 것만)
| 이벤트 `_T` | 쓰는 필드 | 용도 |
|---|---|---|
| LogPlayerPosition | `character.{name,accountId}`, `character.location.{x,y}`, `_D` | 위치 시계열. **좌표는 cm — /100으로 m 변환** |
| LogVehicleRide / LogVehicleLeave | `character.{name,accountId}`, `_D` | 차량 탑승 구간 기록 (속도 룰 제외용) |
| LogPlayerAttack | `attackId`, `attacker.{name,accountId}` | 공격 시도 수·피해 이벤트 연결 키 |
| LogPlayerTakeDamage | `attackId`, `attacker.{name,accountId}`, `damage` | 양수 체력 피해 중 공격 ID가 연결된 이벤트 수·총 피해 |
| LogPlayerMakeGroggy | `dBNOId`, `attacker.{name,accountId}`, `_D` | DBNO를 만든 대상 행동 시각 |
| LogPlayerKillV2 | `dBNOId`, `dBNOMaker`, `finisher`, `killer`, `victim.type`, `damageReason`, `_D` | 직접 종료·DBNO 행동 시각 구분, AI 유형 층화, 헤드샷 |
- `_D`는 ISO8601 `...Z` — `fromisoformat(x.replace("Z","+00:00"))`로 파싱 (구현됨)
- 필드는 매치 모드에 따라 결측 가능 — 전 필드 `.get()` 방어 접근 유지할 것
- `accountId`는 v3 target을 안정적으로 연결할 때만 쓰고 v3 Silver parsed 저장 전에 제거한다
- 공식 사전(무기명·맵명 등)이 필요하면 github.com/pubg/api-assets `dictionaries/telemetry/` (샘플 텔레메트리 파일은 이 저장소에 **없음** — 실측 확인)

## 4. 탐지 룰 명세 (`src/detect.py` 상수)
| 룰 | 정의 | 임계값(근거) | 오탐 통제 |
|---|---|---|---|
| R1_speed | 5초 슬라이딩 창 평균 도보 속도 | > 8.5 m/s (전력질주+부스트 상한 근사, 보수적) | **차량 탑승 구간 ±2s 완충 제외** — 이 필터가 핵심. 낙하산·리바이브 이동은 미처리(알려진 한계, README 기재 후보) |
| R2_hit_ratio | 매치 내 유효 damage_events/attacks 비율의 z-score | z > 3.0, 표본: 공격 ≥30회 플레이어 ≥8명일 때만 | `damage>0`이며 같은 플레이어의 `LogPlayerAttack.attackId`와 연결된 이벤트만 분자에 포함; 표본 조건 미달 스킵 |
| R3_kill_burst | 대상 행동 시각 기준 N킬 시간창 | 3킬 / 12초 | DBNO는 `LogPlayerMakeGroggy`, 직접 종료는 `LogPlayerKillV2` 시각 사용; 피해 대상 `type=user_ai` 별도 층화; REVIEW 고정 |
- 같은 플레이어의 R1 연속 신호는 최고값 1건으로 압축 (구현됨)
- 임계값 튜닝은 실매치 돌린 뒤 오탐률 보고 조정 — 조정 시 이 표를 갱신할 것
- `R2_hit_ratio`는 호환용 ID이며 실제 값은 고유 명중률이 아닌 유효 `damage_events/attacks` 프록시다.
  한 공격이 여러 양수 피해 이벤트를 만들 수 있어 값은 1을 넘을 수 있다.
  대상 포함 모집단 z-score에서 `z>3.0`이 가능한 최소 풀은 11명이다. 탐지 룰의 8명 계약은
  유지하되 v2/v3 후보율은 8~10명을 구조적 스킵으로 분리하고 `evaluated`만 분모로 쓴다.
- v2 구현은 top10의 기술 분포와 기존 R2의 `evaluated/skipped/candidate`를 분리 측정한다. 과거
  `v2-r2-baseline-2` 파일은 구 이벤트 계약이며 실제 평가 분모·대상 매핑을 보존하지 않아 재계산하지
  않는다. 다음 API 표본부터 `rules-event-context-2`로 측정한다.

## 5. 리포트 형식 (`reports/review-queue.md`)
상단에 v1 Silver selection과 DQ manifest 기반 구성(매치 수·모드·맵)을 적는다. 신호마다: 마스킹
닉네임(`pla***`) · 룰 한글 설명 · 관측값 vs 기준 · **근거 이벤트 원값 인용**(시각·좌표·수치) ·
R3 피해 대상 유형 층 · 판정은 항상 `REVIEW`. AGENTS.md §3 어휘 경계를 따른다. data manifest의
DQ가 FAIL이면 리포트를 발행하지 않는다.

## 6. v3 구현 계약

- protocol: 새 실행은 `v3-r2-top100-3`·`rules-event-context-2`; top100 전원을 현 룰의 내부
  holdout으로 사용. 완료된 `v3-r2-top100-2`는 구 계약으로 동결·재현만 지원
- snapshot: season·leaderboard·player batch·v1/v2 selection·이전 v3 cohort SHA-256,
  시작·완료 UTC를 동결
- selection: protocol 3은 최근 5개에서 v1/v2 match와 모든 이전 v3 동결 후보를 보충 없이
  제외하고 공유 match를 단일 귀속하며, metadata의 정확한 `squad-fpp`만 채택. protocol 2는
  기존 v1/v2 제외 계약으로 재현
- preflight: init 후 source-reference·귀속 후보가 top100 전원을 덮고 1차 59명·2차 150건의
  이론상 최대 분모가 가능한지 Silver에 기록. FAIL은 `ApiSession` 생성 전 collect 차단
- observation: Bronze에서만 원 ID/이름 사용, Silver/Gold는 `player_key`; 상태·스킵 분모는
  `PLANNING.md` §8.4의 배타적 분류를 그대로 저장
- statistics: 1차 단측 정확 이항 경계, 2차 Wilson·고정 seed player-cluster bootstrap
- rate limit: 마지막 완료 시각(legacy는 요청 시각)부터 7초를 sleep 뒤 재검사한다. 미완료 예약이
  있는 재시작은 monotonic 기준 7초도 대기하며, 예약을 포함한 세션 예산 60회에서 중단한다
- publish: top100 holdout·v1/v2 및 이전 v3 후보 교집합 0·lineage·checksum·분모 등식·비식별 DQ가 모두
  PASS일 때만 Gold 발행
- 실행: `init`은 snapshot, `collect`는 cache/checkpoint 수집, `evaluate`는 오프라인 검증이다.
  `init`·`collect`만 네트워크를 사용한다

## 7. SQL audit 계약

- 입력: `data/manifests/v3/<run_id>.json`에서 dataset이 `r2_observations`, `holdout_validation`인
  artifact를 각각 1개 선택하고 소비 파일의 SHA-256을 재검산한다
- 저장: Python stdlib `sqlite3`의 `:memory:` 연결만 사용하며 DB 파일은 만들지 않는다
- schema: run, staging observation, player dimension, match dimension, R2 observation fact,
  artifact와 lineage edge를 PK, FK, CHECK 제약으로 연결한다. 배타 상태 조건 전체의 `IS TRUE`로
  SQL UNKNOWN을 거부하며 공격 수 미달 상태의 정상적인 NULL은 유지한다
- query: 조건부 집계로 배타 분모, `ROW_NUMBER`로 player별 첫 evaluated, 재귀 CTE로 빈 rank decile과
  Gold에서 source까지의 lineage를 계산한다
- 발행: SQL 결과가 기존 Gold의 분모, 1차 표본, map, rank decile과 일치하고 lineage cycle이 0일 때만
  `reports/sql-audit.md`를 원자적으로 쓴다
- 경계: 완료된 protocol의 관계형 재검산이며 탐지 성능, 전체 모집단과 운영 DB 능력을 추가로 주장하지 않는다
- 실행: `python -m src.sql_audit --run-id <run_id>`, 네트워크 호출 0회

### 7.1 Semantic shadow sidecar 계약

- 입력: DQ PASS인 `data/manifests/v3/<run_id>.json`과 그 Manifest가 선언한 Bronze, Silver, Gold
  artifact만 읽고 모든 byte 수와 SHA-256 및 lineage source 존재를 재검산한다
- protocol: `v3-r2-top100-2`는 `rules-event-count-1`, `v3-r2-top100-3`은
  `rules-event-context-2`에만 연결하며 명시값 충돌은 실패시킨다
- 모델: HTTPS vocabulary 아래 class 9개, project object property 9개, datatype property 40개와
  PROV-O 계보를 blank-node-free RDF graph로 투영한다
- 검증: SHACL Core closed shape 9개, Meta-SHACL, 로컬 SPARQL CQ 6개, 기존 `graph_spike`와
  `sql_audit` parity, 원 identity exact token 0건, secret marker 0건, blank node 0건을 요구한다
- 재현: UTF-8 N-Triples line을 byte 정렬하고 gzip `mtime=0`을 고정한다. 동일 bytes가 아니면
  write-once 출력을 덮어쓰지 않는다
- runtime: semantic Manifest가 기록한 Python과 dependency version이 달라지면 graph가 같아도
  Manifest byte가 달라 write-once가 중단한다. 전체 bundle 재검증은 기록된 runtime에서 실행한다
- 발행: `data/gold/v3/<run_id>/semantic.nt.gz`, `semantic-validation.json`,
  `data/manifests/semantic/v3/<run_id>.json`을 쓰며 기존 v3 Manifest hash는 바꾸지 않는다
- 실패: graph DQ·SQL parity·SHACL·semantic parity 부적합은 semantic Manifest를 쓰지 않고
  `reports/semantic-validation-<run_id>.json` 진단을 갱신한다. 상세 report가 없는 graph/SQL
  실패는 원문 없는 `stage`·`conforms=false`를 남긴다. 성공 시 같은 run의 과거 실패 진단을 제거한다
- 보안: repository 내부 고정 파일만 parse하고 `owl:imports`, 원격 context, SPARQL `SERVICE`와
  update 문을 허용하지 않는다. 실행 중 네트워크 호출은 0회다
- 실행: `python -m src.semantic --run-id <run_id>`, 성공 0, 검증 실패 1, 입력 또는 runtime 오류 2
- 경계: 의미, lineage와 구조 정합성의 shadow 검증이다. REVIEW 정확도와 모집단 일반화 근거가 아니다

## 8. 실행 (인수자용 절차)

아래 v3 명령은 실행기 재현용으로 보존한다. 현재는 §10 독립 참조 중단 조건이 우선하므로 실행하지 않는다.

```bash
cd pubg-telemetry-watch
# .env에 PUBG_API_KEY=... 한 줄 (커밋 금지 — .gitignore 등록됨)
python -m pip install -e .
python -m src.fetch --player <닉네임> --shard steam --limit 3   # 또는 --sample
python -m src.parse && python -m src.detect && python -m src.report  # 기본 rules-event-context-2
python -m src.elite --platform-region pc-as --shard steam --mode squad-fpp --top 10 --matches-per-player 5
python -m src.medallion --versions v1 v2
# v3 네트워크 실행은 같은 --session-id를 유지한다
python -m src.v3 init --run-id <run> --session-id <session> --api-call-limit 60
python -m src.v3 preflight --run-id <run>  # PASS여야 collect 가능
python -m src.v3 collect --run-id <run> --session-id <session> --api-call-limit 60
python -m src.v3 evaluate --run-id <run>
python -m src.graph_spike --run-id v3-20260901-r2  # 네트워크 없는 관계 graph feasibility 감사
python -m src.sql_audit --run-id v3-20260901-r2  # 네트워크 없는 SQL Gold 교차검증
python -m src.semantic --run-id v3-20260901-r2  # 네트워크 없는 RDF shadow 검증
cat reports/review-queue.md
```
키 없이 로직만 검증: `tests/fixtures/TESTMATCH.telemetry.json`을 임시 `data/`에 배치하는 통합 테스트가
parse→detect→report를 실행한다. `python -m unittest discover -s tests -v`의 기대 결과는 fast_B R1
1건 + burst_D R3 1건, driver_C·normal_A 무신호이며 리포트에는 `pla***`와 `REVIEW`만 남는다.

## 9. 검증 상태 (2026-09-04)

아래는 연구 경로의 검증 기록이다. 2026-09-10 로컬 배치 재검증은 [§12](#12-로컬-배치-운영-계약),
최신 진행·종료 상태는 [`PLAN.md`](PLAN.md)를 따른다.

- 공개 합성 매치 통합 테스트: R1 탐지 ✓ / 차량 제외 ✓ / R3 탐지 ✓ / 정상 플레이어 무신호 ✓ /
  리포트 마스킹·`REVIEW` 2건 ✓
- 실 API: `--sample --limit 1` asset URL·원시 gzip 해제 ✓ / 공개 3판 parse→detect→report ✓
- v1 사람 판독: R2 두 건에서 피해량 0·`Damage_DBNO`가 35/39·108/115를 차지했고, R3
  다섯 건 모두 DBNO 정산 문맥을 포함함을 Bronze 원문으로 교차확인. 승인된 protocol 2로
  오프라인 재처리해 REVIEW 7→0건·manifest DQ PASS 확인 ✓ (`ADR 009`, `ADR 010`)
- v2 엘리트 기준선: `pc-as` 현재 시즌 top10, 고유 38판, 기술 관측 30건인 구 protocol 결과를
  보존. 대상 매핑 부재로 새 R2를 소급하지 않았고 legacy manifest DQ PASS ✓
- v3 protocol 2: 실 top100 snapshot·후보 425개·prior 제외 reference 39개를 동결. 8개 세션 437회에서
  ready 93·mode 제외 332·pending/API/data 오류 0. 3,472,209개 이벤트를 처리해 evaluated
  80건·고유 24명·REVIEW 후보 0건, artifact 631개·DQ PASS를 확인했다. 회고 preflight는
  source 92명·owner 90명, 순위 1~10은 2명·4건으로 FAIL이며 DQ WARN으로 분리했다. 사전
  최소치 59명·150건 미달로 결론은 `INTERMEDIATE`며 임계값은 유지 ✓
- v3 protocol 3: 이전 v3 후보까지 포함한 prior 466개를 동결하고 `init` 12회 완료. 같은 시즌·
  top100 95명 중복에서 reference 371건 제외 후 source 31명·owner 30명·후보 119건으로 preflight
  네 조건이 모두 FAIL. prior 교집합 0·snapshot 재현성을 확인하고 collect 미실행 ✓ (`ADR 011`)
- 관계 graph feasibility: protocol 2 Silver observation 93판을 메모리에 투영해 player 4,992개,
  team instance 1,938개, 2판 이상 반복 pair 460개를 재구성했다. 반복 pair는 account 형식 간
  관계 460개였고 observation-roster 93/93, lineage edge 721개, cycle 0, DQ 15/15 PASS를 확인했다.
  당시 spike 판정은 `FEASIBLE_FOR_NEO4J_REVIEW`였고 도입은 하지 않았다 (`ADR 013`). Neo4j
  경로는 기각했고, 파일 기반 ontology를 별도 semantic shadow로 구현했다 (`ADR 015`, `ADR 016`).
- 독립 참조 first-nail: 기존 player 응답 200행과 공식·연구 원천을 감사했으나 동일 player-match
  참조는 양성 0/20·음성 0/20. 중단 규칙을 발동해 API 0회·검증기 미구현으로 일반화 확장 종료 ✓ (`ADR 012`)
- SQL audit: protocol 2 observation 93건을 player 28명, match 93판, fact 93건으로 투영하고
  조건부 집계 80건, window 기반 1차 24명, lineage 721 edge와 depth 3을 기존 Gold와 교차검증 ✓ (`ADR 014`)
- semantic shadow: protocol 2 artifact 631개 checksum을 재검산하고 player 4,992개, team 1,938개,
  match 93개, observation 93개를 51,892 triples로 투영했다. SHACL과 CQ 6/6, 반복 pair 460개,
  lineage 721 edge와 cycle 0, 1차 24명과 후보 0건 parity, raw token과 secret marker 및 blank node
  0건을 확인했다. 기존 v3 Manifest SHA-256은 유지했고 API 호출은 0회다. 실측 24.20초에서
  25.88초, peak RSS 최대 233,204 KB이며 상태는 `SHADOW_VALIDATED`, `NOT_PRODUCTION_GATE`다 (`ADR 016`)

## 10. 중단 상태와 재개 조건
1. 현 일반화 확장 계획은 `STOPPED_NO_MATCH_LEVEL_REFERENCE`다. 새 API 수집을 실행하지 않는다.
2. PLANNING §8.5 적격 참조가 양성·음성 각 20건 모두 확보된 경우에만 별도 승인으로 재개한다.
3. 재개 전에는 라벨 reader·혼동행렬 계산기·manifest를 미리 구현하지 않는다.
4. 완료된 protocol 2와 protocol 3 결과는 합치거나 일반화 근거로 승격하지 않는다.
5. (선택 발표물) README 실행 결과 스크린샷

## 11. Medallion schema 리포트 계약

- 산출물: `reports/medallion-schema.html`
- 집계 기준: JSON 객체의 최상위 key를 물리 필드로 세고, 중첩 객체와 배열은 부모에서 1개로 센 뒤 별도 스키마로 펼친다
- 표기 기준: 저장 파일의 `STORED`와 현재 writer의 `CURRENT`를 분리하고, event type별 합집합을 개별 레코드 필드 수로 해석하지 않는다
- 공개 경계: 필드 이름과 집계만 발행하고 Bronze 원 식별자와 실제 값을 발행하지 않는다
- 해석 경계: manifest PASS는 byte, lineage, schema, 분모 정합성을 뜻하며 REVIEW 외부 정확도와 모집단 일반화를 뜻하지 않는다


## 12. 로컬 배치 운영 계약

기존 연구 계층에 쓰지 않는 오프라인 재처리 경로다. `ADR 018`과 승인된 PLANNING §4의 예외를 따른다.

| 항목 | 계약 |
|---|---|
| 실행 | Linux/WSL, 단일 Worker, `fcntl.flock` 비차단 잠금. 중복 작성자는 `WORKER_BUSY` |
| 저장 | 기본 `~/.local/state/pubg-telemetry-watch/ops.sqlite3`, 로컬 파일시스템의 SQLite WAL·FULL·FK ON |
| 입력 | DQ PASS Manifest의 Bronze telemetry와 매치 metadata/selection. 입력 경로 탈출·bytes·records·JSON 객체 구조 검증. 실제 파싱할 동일 byte의 SHA를 확인 |
| protocol | v1 rules-1/context-2, v2 baseline-2/3, v3 top100-2/3을 기존 룰 protocol에 대응. 한 배치는 단일 protocol |
| 계산 | `parse_events`와 `detect_match`를 기존 CLI와 공유. 기존 v3 parsed 비식별 함수와 동일한 key 계산 |
| 중복 | 입력 SHA·match ID·룰 protocol·실행 Python/SQL 내용 해시·Python/SQLite 버전으로 job ID 생성. 여러 배치가 같은 job을 참조 |
| 소스 범위 | 내용 해시는 정렬한 `src/**/*.py`와 `sql/**/*.sql` 전체를 포함한다. 중첩 구현 변경도 새 identity이며 문서 변경은 포함하지 않음 |
| 상태 | QUEUED → RUNNING → SUCCEEDED/FAILED. 잠금 확보 뒤 남은 RUNNING은 INTERRUPTED 시도 기록 후 QUEUED |
| 원자성 | 한 매치의 combat_event·player_match·review_signal·review_case·최초 history와 SUCCEEDED를 한 트랜잭션에 저장 |
| 재시도 | FAILED는 명시적 retry만 QUEUED로 전환. 입력 문제는 격리하고 DB 장애는 Worker 종료 |
| 검산 | 원시 공격/피해 투영으로 EXISTS·조건부 집계·window 계산. Python과 건수·상태·후보 일치, math.isclose의 상대·절대 허용 오차 각각 1e-9 |
| 비식별 | DB와 리포트에 원 이름·account ID를 적재하지 않는다. combat event는 비식별 key와 원문 배열 index로 연결 |
| 조회 수명 | review list/show·status·report는 read_snapshot port를 사용한다. transaction이 없으면 조회가 열고 정상·예외 모두 종료한다. 기존 읽기/쓰기 transaction은 재사용하며 commit/rollback하지 않아 caller의 미커밋 변경과 종료 책임을 보존한다 |
| 발행 | 작성자 잠금으로 Worker/동시 발행과 충돌 차단. operations JSON/Markdown은 진행 상태도 표현. 전체 성공 시 REVIEW와 checksum Manifest를 마지막에 원자적으로 발행 |
| 보고서 snapshot | status와 결과 조회는 같은 snapshot을 공유한다. report가 연 snapshot은 파일 발행 전에 종료한다. 기존 transaction을 빌렸다면 파일 발행 중에도 수명은 caller가 관리한다 |
| 재현 | `render_review`에 저장된 완료 시각을 전달. 동일 완료 결과는 같은 보고서 byte를 생성 |
| 계측 | load, parse_detect, SQL, commit 시간·p50/p95와 표본 수·오류/재시도. 성공 elapsed_s는 처리 시작부터 성공 커밋 직후까지이며 후속 계측 저장 전 종료 시 NULL; 성공을 되돌리지 않는다. 기존 process_peak_rss_kib는 커밋 전 VmHWM으로 보존. 하니스는 GNU Time으로 run/report 각각 종료까지 peak RSS(KiB)를 별도 기록 |
| 경계 | 기존 SQL audit은 :memory: 유지. 원 연구의 cohort 분모·Gold·semantic Manifest를 변경하지 않는다 |
| 검토 case | review_case(case_id PK), UNIQUE(job_id,player_key,rule), 기존 신호에 composite FK. OPEN → IN_REVIEW → COMPLETED; reopen은 OPEN. REVIEW 판정과 분리 |
| 검토 이력 | review_history(case_id,sequence PK), operator label·UTC·action·전후 상태·note. 현재 상태와 같은 트랜잭션, UPDATE/DELETE trigger로 append-only. 인증된 사용자 신원은 아님 |
| schema | user_version=2, 새 빈 DB만 초기화. 이전 version은 journal 설정 변경 전에 UNSUPPORTED_DATABASE_SCHEMA로 거부, 자동 migration 없음 |
| 검증 도구 | SQL source inventory와 계약의 배타적 문서 소유권을 검사. namespace 격리가 확인된 뒤 tests/demo 실행; 격리 실패를 skip하지 않음. offline_check의 선택형 record-dir은 namespace→설정된 mypy→tests→demo→SQL 순서와 실제 명령·범위·종료 코드·시간·로그, 소스/테스트/fixture/도구/설정/공개 문서 SHA 및 환경 버전을 기록한다. 기존 결과 경로는 거부하며 실패·중단·미실행·실행 전후 조건 변경은 PASS가 아니다. validation_status는 schema 1·필수 단계/필드·조건 hash·성공 일관성과 로그 읽기 가능 여부를 검사하고 과거 결과와 현재 파일/환경 일치를 분리한다. 현재 완료 PASS만 exit 0, 유효한 기록의 실패/미완료/로그 누락/조건 불일치는 1, 기록/현재 조건 조회 오류는 2다. 원본 수정·명령 재실행·사람용 로그 파싱은 없고 RUNNING은 실제 실행 중일 수 있다. 운영 runtime 지문·기존 비기록 호출은 유지. walkthrough의 assert 비활성 실행은 거부 |
| 도식 보안 | Dnn ID·좌표·색 검증, label escape, embedded SVG의 안전 요소/속성 및 class별 정적 fill 색만 허용. 원격 참조·script·CSS import 차단; docs/security/operations.md |
| 클라우드 종료 사전점검 | 별도 로컬 `private/cloud-retirement/20261101/`에서 지정 프로젝트 전체의 종료 기한·증빙·삭제 제약을 관리한다. 현 코드는 로컬 증거의 scope·신선도·checksum·경로를 검사하며 삭제·예약 기능은 없다. 전수 목록·외부 실행기·보존 정책·복원 증거가 미확인이면 BLOCKED; `ADR 020` |

실행은 `python -m src.ops run --batch-id <id> --manifest <path>`다. 같은 인수로 재개하며 Manifest를
생략하면 등록된 입력을 쓴다. `status --batch-id <id> --json`, `retry --batch-id <id> --job-id <id>`,
`report --batch-id <id>`, `demo`를 제공한다. 모든 명령은 `--state-dir`를 지원하고 run의
`--source-root` 기본값은 저장소 루트이며 Manifest 내부 상대 경로의 기준이다. DB는 `<state-dir>/ops.sqlite3`, 보고서는 `<state-dir>/reports/<batch_id>/`에 둔다. Python/SQLite 버전이 달라지면 기존 배치 재개를 차단하고 새 배치로 등록한다. demo는 코드와 Python/SQLite 버전으로 배치 ID를 자동 생성한다. 성공 0, 미완료 배치 1, 입력/상태/DB 오류는 고정 JSON 진단과 exit 2다.

공개 demo는 기존 53-event TESTMATCH와 R2 합성 입력을 사용한다. 별도 `src.ops_demo` 명령은
고정 seed의 1M/10M 부하와 동결 실 데이터의 준비 실행 1회·측정 3회를 새 DB에서 수행한다.
원본 압축 여부·byte·이벤트 수와 환경을 함께 기록하며, 합성 부하를 외부 정확도 표본으로 해석하지 않는다.

하니스의 처리량은 새 성공 이벤트 수 / (run+report 초), E2E는 준비된 입력으로 run 시작부터
report 프로세스 종료까지다. 입력 생성·정합 비교는 제외한다. 준비 1회와 측정 3회는 각각 새 DB·프로세스를
사용하고 기존 측정 디렉터리 재사용은 거부한다. `--match-events`로 단일 매치 크기를 분리 측정한다.
같은 버전은 결과 해시, `--compare-to` 버전 간 비교는 UTF-8 JSON을 읽어 합성 actor ID에 대응한 신호·측정값을 비교한다.
정수·룰·근거는 정확히 비교하고 실수만 기존 parity의 상대/절대 1e-9를 사용한다. 운영 player_key 계약은 유지한다.

`review list [--batch-id ID] [--state OPEN|IN_REVIEW|COMPLETED]`, `review show --case-id ID`,
`review start|complete|reopen --case-id ID --operator LABEL`,
`review note --case-id ID --operator LABEL --note TEXT`는 모두 `--state-dir`를 지원한다.
목록은 created_at·case_id 순, 이력은 sequence 순이다. 빈 operator/note·없는 case·잘못된 전이는
고정 JSON 오류와 exit 2로 거부한다. note는 어느 업무 상태에서도 추가할 수 있고 이전 메모를 수정하지 않는다.
같은 job 재사용·retry·report는 검토 상태를 초기화하지 않는다. 새 코드/runtime의 job은 별도 case다.

2026-09-09 코드의 검증 기록: 공개 43건, 동결 723개 SHA, 기존 SQL audit 13/13, 실 입력 134판·5,053,469개 이벤트가 통과했다. 5개 입력군의 총 20회 결과 해시가 일치했고, 1M/10M run 중앙값은 10.52/113.85초, 시도별 기록 RSS 최대는 86,264/86,428KiB였다. 매치당 최대 4만 이벤트 조건의 RSS 증가는 0.19%다. 당시 EXPLAIN은 현행 protocol 매개변수에 고정된 설명용 계획이었다. 현 하니스는 배치 protocol을 기록하고 그 매개변수로 계획을 수집한다. 환경·원자료·측정 한계는 [README](README.md#로컬-배치-실행과-sql-검산)를 따른다.

2026-09-10 검증: 검사 직후 입력 교체, runtime 변경 demo, 잘못된 Manifest와 token의 CLI 오류 계약을 추가해 공개 46건을 Python 3.10·3.11·3.12에서 통과했다. 수정 코드로 실 입력 134판, 기존 SQL audit 13/13, 동결 파일 723개 SHA를 재검증했다. 1M 실행 확인은 준비 1회·측정 1회이며 과거 1M/10M 3회 비교와 구분한다.

## 13. 실행 코드의 책임 분리

| 계층/구현 | 소유 책임 | 금지/검증 경계 |
|---|---|---|
| domain/pubg 및 domain | parse/detect, cohort·통계·품질, review 전이, 식별자·lineage 계산 | 외부 I/O·CLI·SQL·현재 시각 없음; 기존 룰과 분모 보존 |
| application/operations | 등록·복구·처리·명시적 retry·review·status·report 순서와 조회 범위 | SQL/SQLite 연결은 port 밖으로 노출하지 않음; 결과·사람 이력 원자성, 중첩 조회 snapshot 유지 |
| application/pipeline, collection, research, medallion | 기존 v1/v2/v3 실행과 고정 원장·발행 순서 | Files·Clock·HTTP port; 신규 수집 없이 합성·오프라인 회귀 |
| application/graph_audit, sql_audit, semantic | 파일 조회·독립 계산 결과 대조·semantic 발행 | SqlAudit.read는 보고서 쓰기 없이 조회; RDF/SHACL은 adapter; semantic graph/SQL 부적합도 안전한 단계 진단을 갱신 |
| adapters/sqlite_ops, sqlite_audit, sqlite_benchmark | 실행 SQL·스키마·바인딩·조회·실행계획; read_snapshot의 transaction 소유권 | SQL 목록은 Class.method까지 연결; 고정 식별자 목록; schema v2 유지; 직접 연 조회 transaction만 종료 |
| adapters/files, credentials, http, clock, environment, provenance | 파일·비밀키·HTTP·시각·실행환경·전체 소스 지문 | 비밀값은 HTTP 경계에만; 실제 소비 byte 검증; atomic/write-once 유지 |
| adapters의 presentation 및 rdf | 검증된 결과의 Markdown/RDF/SHACL/SPARQL 표현 | 기존 report byte와 결정적 gzip/JSON 계약 유지 |
| cli 및 기존 src 진입점 | 인수·출력·exit·adapter 조립·resource 수명 | 기존 명령/호출 인수 유지; 구현 모듈로 역참조하지 않음 |
| tests/tools 및 개발 CI | 계층·cycle·보안·장애 회귀, GNU Time 성능·SQL·도식 검사; 고정 mypy의 단계적 정적 검사와 실행 기록·판독 | `pyproject.toml`의 기존 runtime 4개와 validation_status 총 5개 파일·Python 3.10 계약·주석 없는 함수 본문 검사, import된 범위 밖 진단과 Any의 타입 보장은 제외; CI 3.10/3.12에서 실행하고 기록과 같은 권한/인터프리터로 판독 JSON을 출력한 뒤 별도 always 단계에 원본 JSON·로그를 남김. SQLite 조회 오류 주입 뒤 허용 callback으로 복구해 Python 3.10~3.12에서 검증; namespace 격리 실패를 PASS/skip 처리하지 않음. 기록·판독 회귀는 실제 user/network namespace·하위 프로세스·파일로 성공·실패·중단·보존·손상/누락·조건 불일치를 검사 |

검토 조회는 기존 signal·case·history를 읽고 탐지를 재실행하지 않는다. 업무 완료는 REVIEW 판정을
바꾸지 않는다. event/processing/review 시각, protocol·출처·분모·결측·단위는 별도 의미로 유지한다.
R1 끝점은 전체 이동 경로가 아니며 전체 replay·UI·다른 게임 지원은 별도 데이터 계약과 구현 범위다.
도식·조회 계약·폴더 소유권은 [Clean Architecture](docs/architecture/clean-architecture.md),
결정은 [ADR 022](docs/adr/022-clean-architecture-boundaries.md), 실제 수행 결과는
[리팩터링 검증](docs/maintenance/refactoring-validation.md)에 둔다.

조회 수명의 후속 결정은 [ADR 024](docs/adr/024-owned-read-snapshots.md), 검증은
[조회 snapshot 검증](docs/maintenance/read-snapshot-validation.md)을 따른다.
