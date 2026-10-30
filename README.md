# PUBG Telemetry Watch

> PUBG 공식 API와 telemetry의 매치 이벤트를 Bronze·Silver·Gold, SHA-256 계보와 DQ Manifest로 검증하고, 룰 기반 신호를 사람 검토 큐(`REVIEW`)로 낸다. 동결 입력의 로컬 배치는 단일 Worker와 영속 SQLite로 중단 복구, 원시 이벤트 SQL 검산과 완료 결과 재사용을 제공한다. 완료된 v3는 in-memory SQLite와 RDF semantic shadow로 기존 결과의 관계·의미·계보를 다시 검산한다. 표본 미달과 실험 중단 상태를 함께 공개하며 탐지 정확도를 주장하지 않는다.
>
> | 단계 | 표본 | 결과 |
> |---|---|---|
> | v1 | 공개 sample 3판, 원시 106,792 이벤트 | 구 룰 REVIEW 7건 → 원시 이벤트 판독 후 새 룰 0건 |
> | v2 | legacy `rules-event-count-1`: 리더보드 top10, 38판 | R2 기준선 산출(z>3 1/30). 모드 혼합으로 매치별 후보율은 산출하지 않음 |
> | v3 | legacy protocol 2: 고정 후보 425 match·API 437회·3,472,209 이벤트; 현행 protocol 3: preflight만 실행 | protocol 2는 0/24·0/80, Wilson 상한 4.58%, `INTERMEDIATE`; protocol 3은 수집·평가 미실행 |
> | semantic shadow | 완료된 v3 protocol 2, 기존 artifact 631개 | 51,892 triples, SHACL PASS, CQ 6/6, 원 identity token 0건 |
> | first-nail | 적격 독립 참조 양성 0/20 · 음성 0/20 | `STOPPED_NO_MATCH_LEVEL_REFERENCE`, 평가 코드 미작성 |
> | 로컬 배치 | 동결 134판·5,053,469 이벤트, 합성 1M/10M 부하 | 재처리·원시 이벤트 SQL 일치, 중단 복구·중복 재사용 회귀 통과 |

배틀그라운드 공식 개발자 API의 매치 텔레메트리를 수집해 룰 기반 이상 신호와 근거 이벤트를
`reports/review-queue.md`에 정리한다. 결과는 자동 확정이 아니라 사람이 확인할 검토 큐다.

## 파이프라인

```text
PUBG API / telemetry CDN
          ↓
Bronze 원문(write-once) → Silver 검증·정규화(v3 비식별) → Gold 신호·통계
          └──────────── data manifest(SHA-256·lineage·DQ) ─→ REVIEW report
                                      └─→ in-memory SQLite audit
                                      └─→ RDF semantic shadow + 별도 manifest

동결 Bronze + Manifest → 로컬 Worker → 영속 SQLite → 운영/REVIEW report
```

새 수집은 gzip을 해제하기 전에 수신 byte를 Bronze에 보존한다. 기존 v1/v2 해제 JSON도 삭제하지
않고 `legacy_decoded_json`으로 계층화했다. 일반 파일시스템에서 처리하므로 분산 저장소의 보장을
주장하지 않으며, atomic replace·checksum·품질 게이트가 제공하는 범위만 보장한다.

2026-10-30 공개 CI·새 clone·GCP의 92개 검사와 합성 장애 복구를 확인했다. 1M/10M 클라우드 측정과 독립 백업 복원 결과는 [운영 runbook](docs/operations-runbook.md#gcp-staging-status)에 기록했다. 프로젝트 전체 종료와 자동 삭제 예약은 별도 미완료다.

## 버전별 검증 목표

| 버전 | 확인하려는 것 | 현재 상태 |
|---|---|---|
| v1 MVP(1~2일) | 실 API 데이터가 근거 리포트까지 end-to-end로 흐르는가 | 공개 3판 완료 |
| v2 후속 실험 | 정상 상위권이 현 R2에서 과도하게 REVIEW 후보가 되는가 | legacy 룰의 top10 초기 기준선 완료 |
| v3 장기 로드맵 | 모드 통제·기존 match 제외 top100 내부 holdout에서 v2 결과가 재현되는가 | legacy protocol 2는 425/425·`INTERMEDIATE`; 현행 protocol 3은 preflight 중단 |
| 외부 일반화 gate | 독립 player-match 참조로 동결 룰을 검증할 수 있는가 | 엄격 적격 0/20+0/20, 계획 중단 |

표본 계약·지표·해석 범위·성공/중단 조건의 정본은
[`PLANNING.md` §8](PLANNING.md#8-버전별-실험-계약-목표방법론-정본)이다.
통계 근거는 [`v3-statistical-validation.md`](docs/methodology/v3-statistical-validation.md), 데이터
계약은 [`medallion-data-pipeline.md`](docs/architecture/medallion-data-pipeline.md)에 있다.

## 설치

Python 3.10 이상이 필요하다. 로컬 배치와 이를 포함한 전체 회귀 검사는 Linux/WSL에서 실행한다.

```bash
git clone https://github.com/procloudkim/pubg-telemetry-watch-portfolio.git pubg-telemetry-watch
cd pubg-telemetry-watch
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

설치 후 공개 합성 매치를 포함한 전체 회귀 게이트를 실행한다. `python` 명령이 없는 환경에서는
같은 명령의 `python`을 `python3`으로 바꾼다.

```bash
python -m unittest discover -s tests -v
```

개발용 타입 검사는 저장소 루트에서 아래 명령으로 실행한다. 실행 의존성과 별개인
`typecheck` extra가 mypy 버전을 고정하고, 로컬과 CI는 같은 `pyproject.toml`을 사용한다.

```bash
python -m pip install -e ".[typecheck]"
python -m mypy --config-file pyproject.toml
```

범위는 `src/` 아래 `application/ports.py`, `application/operations.py`, `adapters/sqlite_ops.py`,
`cli/ops.py`와 `tools/validation_status.py`의 5개 파일이며 Python 3.10 문법·타입 계약을 기준으로 검사한다.
`check_untyped_defs`로 주석 없는 함수 본문도 검사하되, `Any`인 인수·반환값의 타입까지
보장하지 않는다. `follow_imports="silent"`는 가져온 모듈의 타입 정보를 사용하면서 그
모듈의 진단은 제외한다. 나머지 코드·테스트·도구의 타입 검사는 아직 게이트에 포함하지 않는다.
CI는 Python 3.10·3.12에서 namespace 격리 후 이 검사와 기존 오프라인 회귀를 실행한다.
`tools/offline_check.py --record-dir <새 경로>`로 같은 검사의 실행 조건·단계별 결과·로그를
남긴다. `python tools/validation_status.py <result.json>`은 과거 결과와 현재 조건 일치를 구분해
JSON으로 표시한다. exit 0은 현재 조건이 일치하고 필수 로그를 읽을 수 있는 완료 PASS,
exit 1은 실패·미완료·근거 누락·조건 불일치, exit 2는 기록/현재 조건 조회 오류다.
[오프라인 게이트 명령과 기록 해석](docs/operations-runbook.md#offline-gate)을 따른다.
기록 회귀는 Linux user/network namespace를 실제 생성하므로 해당 권한이 필요하다.

API 수집 명령에만 저장소 루트 `.env`의 `PUBG_API_KEY=<발급받은 키>`가 필요하다. 합성 demo와 오프라인 재처리에는 키가 필요 없다. `.env`, `data/`, `reports/`는 커밋하지 않는다.

## v1 — 공개 표본 3판

```bash
python -m src.fetch --sample --limit 3 --shard steam
python -m src.parse
python -m src.detect
python -m src.report
python -m src.medallion --versions v1
```

2026-09-01 실측 표본은 3판(`squad` 2, `squad-fpp` 1), 맵은 `Baltic_Main` 2판과
`Tiger_Main` 1판이었다. 구 `rules-event-count-1`은 원시 이벤트 106,792개를 순회하고 관련
이벤트 51,995개를 집계해 REVIEW 신호 7건을 만들었다. 아래는 당시의 마스킹된 예시다.

```text
[R3_kill_burst] pla***
관측값 3 / 기준 3 kills/12s
근거 이벤트: kill_times=[1788132836.5, 1788132840.7, 1788132846.8]
판정: REVIEW
```

2026-09-02 사람 판독에서는 R2 두 건의 39·115개 피해 이벤트 중 각각 35·108개가 피해량 0인
`Damage_DBNO` 상태 이벤트였고, 실제 공격 ID와 연결된 양수 피해만으로 진단 재계산한 z는
0.65·-0.32였다. R3 다섯 건은 모두 DBNO 정산을 포함했다. 승인된 `rules-event-context-2`는
groggy 246건을 포함한 관련 이벤트 52,241개를 집계해 같은 3판에서 REVIEW 0건·DQ PASS를 냈다.
AI 유형은 제거하지 않고 향후 R3 신호의 별도 층으로 남긴다. 근거와 결정은
[`ADR 009`](docs/adr/009-v1-human-review.md)와
[`ADR 010`](docs/adr/010-event-context-rule-protocol.md)에 있다.

## v2 — 엘리트 R2 기준선

v1과 같은 API 세션에서 이어 실행하면 인증 API 총 60회를 넘지 않도록 56회로 제한한다.
각 인증 요청 사이는 코드에서 7초 이상 대기한다.
[공식 규정](https://documentation.pubg.com/en/rate-limits.html)상 `/matches`와 telemetry 엔드포인트는 rate limit 대상이 아니며 API 키 한도에 계산되지 않는다. 60회·7초는 공식 한도가 아니라 이 프로젝트가 스스로 정한 계약이다.

```bash
python -m src.elite --platform-region pc-as --shard steam --mode squad-fpp \
  --top 10 --matches-per-player 5 --api-call-limit 56
```

2026-09-01 현재 시즌 구 protocol 실측은 `squad-fpp` 리더보드 top10의 최근 2~5판(평균 4.4), 고유
38판이었다. 최근 매치는 모드로 재필터링하지 않아 여러 모드가 섞였다. 공격 30회
이상 기술 관측 30건/9명의 `damage_events/attacks` 프록시 평균은 0.4259, 표준편차는
0.5248이었다. 통합분포의 z>3 후보는 1/30(3.33%)이었고 현 매치별 R2 후보 기록은 0건이다.
다만 과거 파일에는 실제 `evaluated/skipped` 분모가 없어 `0/30` 또는 0%로 해석하지 않는다.
임계값은 변경하지 않았으며 결정 근거는
`docs/adr/001-elite-r2-baseline.md`에 있다.
이 legacy 파일은 대상 매핑이 없어 새 R2로 소급하지 않는다. 다음 수집부터 양수 피해와 공격 ID가
연결된 `rules-event-context-2`를 사용한다.

## v3 — top100 내부 holdout

> 현재는 독립 참조 gate가 중단 상태이므로 아래 네트워크 명령을 실행하지 않는다. 기존 실행의
> 재현 절차로만 보존한다.

완료된 프로토콜 `v3-r2-top100-2`는 v2를 탐색 단계로 두고 top100 전원을 당시 룰의 내부 holdout으로
사용한다. 플레이어별 API 순서 앞 5개에서 v1/v2 match를 보충 없이 제외하고, 공유 match는 한
명에게만 귀속하며, metadata가 정확히 `squad-fpp`인 match만 분석한다. 1차는 플레이어당 첫 평가
완료 1건의 단측 95% 정확 이항 경계, 2차는 모든 평가 완료 관측의 Wilson 구간과
player-cluster bootstrap이다.

새 실행은 `v3-r2-top100-3`으로 분리하며 R2 분자에 양수 피해·공격 ID 연결 계약을 적용한다.
이 protocol은 v1/v2 match와 모든 이전 v3 동결 후보를 최근 5개에서 보충 없이 제외하고,
그 source hash와 교집합 0을 DQ에 고정한다. 완료된 protocol 2의 제외 정책과 산출물은 바꾸지 않는다.
R2 값은 여전히 고유 명중률이 아닌 유효 `damage_events/attacks` 프록시다. 공격 30회 이상 플레이어 풀이
8명 미만이면 일반 표본 스킵, 8~10명이면 `z>3.0`이 수학적으로 불가능한 구조적 스킵, 11명
이상만 평가 분모로 센다. 이 경계와 후보 여부는 서로 배타적인 상태로 저장한다.

네트워크 단계에는 사람이 정한 session ID가 필수다. 같은 세션의 `init`과 `collect`는 같은 ID를
써야 하며, 합계 60회에 도달하면 새 세션 ID로 재개한다. 성공 cache는 다시 호출하지 않는다.
호출 원장은 단일 수집 프로세스를 전제로 하므로 `init`·`collect`를 병렬 실행하지 않는다.
새 원장에는 요청 전 예약과 요청 종료 기록이 연결된다. 강제 종료로 완료 여부가 불명확한 예약도
예산에서 차감하며, 손상된 원장은 새 요청을 차단한다. 기존 완료 원장은 그대로 읽는다.

```bash
python -m src.v3 init --run-id <season-run> --session-id <session-1> --api-call-limit 60
python -m src.v3 preflight --run-id <season-run>  # PASS여야 collect 가능
python -m src.v3 collect --run-id <season-run> --session-id <session-1> --api-call-limit 60
# 예산 소진 뒤 같은 run을 새 세션으로 재개
python -m src.v3 collect --run-id <season-run> --session-id <session-2> --api-call-limit 60
python -m src.v3 evaluate --run-id <season-run>
```

합성 top100에서는 기존 표본 대역 1개를 제외해 전체 오프라인
평가 경로를 검증했다. holdout 100명, 1차 99명, DQ PASS, prior match 교집합 0과 Silver/Gold
비식별이 재현됐다. 이 합성값은 실험 결과가 아니라
실행기 검증값이다. 실 v3 완료에는 1차 59명과 2차 평가 완료 150건이 모두 필요하다.

protocol 2 실 snapshot(채취 2026-09-01 13:20:50 UTC, 평가 완료 2026-09-02 00:50:46 KST)은 top100, 공유 match 단일 귀속 뒤 고정 후보 425개다. v1/v2와 겹친
최근 reference 39개는 뒤 순번 보충 없이 제외했다. 인증 API 8개 세션 437회로 전량 처리해
`ready=93`, `mode_excluded=332`, `pending=0`, API·data 오류 0으로 종료했다. 준비된 93판의
3,472,209개 이벤트에서 `evaluated=80`, `target_below_min_attacks=9`,
`match_pool_below_8=2`, `match_pool_below_signal_capable=2`로 분모 등식이 일치했다.

1차 결과는 REVIEW 후보 0/24명으로 사전 최소 59명 미달이다. 2차는 0/80건,
Wilson 95% 구간 0~4.58%였지만 사전 최소 150건에 미달했다. 따라서 수치적 상한이 5%
아래여도 운영 기준을 지지한다고 결론내지 않고 최종 상태를 `INTERMEDIATE`로 동결했다.
평가 관측은 `Baltic_Main`·`Desert_Main`·`Neon_Main`·`Tiger_Main` 순으로
19·20·21·20건이었고 순위 1~10 구간은 평가 관측이 0건이어서, 대상 모드
필터 후 커버리지가 top100 전체를 대표하지 않는다. 회고 preflight는 reference 보유
92명·단일 귀속 후보 소유 90명으로 FAIL이었고, 순위 1~10은 prior 제외 39건이 집중돼
2명·4건만 남았다. 따라서 v3 실결과는 top100 전체가 아닌 가용성 조건부 24명의 결과다.

Gold manifest는 artifact 631개의 checksum·lineage, snapshot 재현성, prior 교집합 0,
Silver 비식별을 검사해 DQ PASS다. 첫 세션에서 원장 기준 7초보다 0.001314초 짧은 호출 간격과
회고 코호트 커버리지 FAIL을 WARN 2건으로 보존했고, 마지막 세션 최소 간격은 7.000120초다. 결과를 본 뒤
현 표본을 늘리거나 임계값을 바꾸지 않았다. 종료 결정은
`docs/adr/007-v3-frozen-sample-closure.md`, 후속 fail-fast은 `docs/adr/008-v3-collection-preflight.md`다.
protocol 2 artifact 631개는 checksum PASS 상태로 보존하며 새 룰로 사후 재계산하지 않았다.

2026-09-02 protocol 3 첫 `init`은 이전 표본 466개를 제외한 새 snapshot을 인증 API 12회로
동결했다. 같은 시즌 top100 중 95명이 protocol 2와 겹쳤고 최근 reference 371건이 제외되어,
source 31명·owner 30명·고유 후보 119건만 남았다. 이전 후보와 교집합은 0이지만 1차 최대 30명
및 2차 최대 119건으로 사전 최소 59명·150건에 못 미쳐 preflight FAIL로 collect를 시작하지 않았다.

사전 운영 기준은 정상 참조군 1차 후보율 5% 미만이다. 사람 판독 전에는 확정 오탐률이 아니라
`REVIEW` 후보율로만 해석한다. 사람 판독은 실험·검증이 끝난 뒤 사용자 요청 시 별도 수행하며
v3 완료를 막지 않는다. 어떤 통계 결론도 승인 없이 R2 임계값을 바꾸지 않는다.

## SQL로 Gold 재검산

완료된 protocol 2의 비식별 Silver observation과 manifest를 Python stdlib `sqlite3`의
`:memory:` 데이터베이스에 투영한다. 데이터베이스 파일과 새 Gold를 만들지 않으며 API도 호출하지 않는다.

```bash
python -m src.sql_audit --run-id v3-20260901-r2
```

```text
SQL audit: PASS observations=93 evaluated=80 primary=24 candidates=0
```

[`sql/v3_audit.sql`](sql/v3_audit.sql)은 다음 관계형 처리와 검사를 실행한다.

| SQL 기능 | 검증 대상 | 실측 결과 |
|---|---|---:|
| PK, FK, CHECK | player, match, observation 관계와 배타 상태 | 93 fact 적재 |
| 조건부 집계 | evaluated와 세 가지 skip 분모 | 80, 9, 2, 2 |
| `ROW_NUMBER` window | player별 첫 evaluated match | 24명 |
| 재귀 CTE | Gold에서 source까지 lineage | 721 edge, depth 3, cycle 0 |
| Gold 교차검증 | 분모, map, rank decile, 1차 표본 | 13/13 PASS |

공개 CI는 합성 observation으로 SQL 제약, window 선택, 빈 rank decile과 실패 동작을 검증한다.
위 93건 결과는 커밋하지 않은 로컬 v3 데이터의 checksum을 기준으로 재현했다. 이 SQL audit은
완료된 결과의 관계형 재검산이며 탐지 성능이나 전체 모집단 결과를 추가로 입증하지 않는다.
결정 근거는 [`ADR 014`](docs/adr/014-in-memory-sql-audit.md)에 있다.

## 로컬 배치 실행과 SQL 검산

동결 Manifest의 telemetry를 매치별로 재처리하고, SQLite에 실행 이력·비식별 공격/피해 이벤트·결과를 저장한다. 기존 파서와 R1/R2/R3를 공유하며 SQL은 원시 공격·피해 연결, R2 분모와 z-score를 재계산한다. Python과 건수·상태·후보가 일치하고 실수가 `math.isclose(rel_tol=1e-9, abs_tol=1e-9)`를 만족하는 결과만 커밋한다. 기존 연구 결과의 SQL audit은 별도의 in-memory 경로로 유지한다.

Linux/WSL에서 키와 로컬 실 데이터 없이 시작할 수 있다.

```bash
python -m src.ops demo
```

기존 TESTMATCH와 R2 합성 매치를 처리해 성공 작업 2건·REVIEW 3건을 만들고, 재등록 시 실행 시도가 늘지 않는지 검사한다. demo 배치 ID에는 코드와 Python/SQLite 버전이 반영된다. 실행 디렉터리는 기본 `~/.local/state/pubg-telemetry-watch/`이며, 결과 경로를 터미널에 출력한다.

실 입력은 DQ PASS Manifest와 그 안에 선언한 telemetry 및 매치 metadata/selection 파일을 준비한다. [Manifest 최소 스키마](docs/architecture/medallion-data-pipeline.md#manifest-최소-스키마)를 따르며, 내부 `artifact.path`는 `--source-root`를 기준으로 해석한다. 기본값은 저장소 루트다. 각 명령은 `--state-dir <로컬 경로>`를 지원한다. DB와 잠금 파일은 Linux 파일시스템에 두고 Windows 공유 마운트는 입력 경로로 사용한다. [SQLite WAL의 저장·동시 접근 조건](https://www.sqlite.org/wal.html)을 따른다.

```bash
python -m src.ops run --batch-id replay-v1 --manifest data/manifests/v1.json
python -m src.ops status --batch-id replay-v1 --json
# 중단된 작업 재개: 완료 작업은 재사용
python -m src.ops run --batch-id replay-v1
# 실패 작업은 원인을 수정한 뒤 명시적으로 재시도
python -m src.ops retry --batch-id replay-v1 --job-id <status에 나온 job_id>
python -m src.ops run --batch-id replay-v1
python -m src.ops report --batch-id replay-v1
```

| 상황 | 처리 |
|---|---|
| 중복 등록 | 같은 입력 SHA·match·protocol·구현 해시·Python/SQLite 버전의 작업을 재사용 |
| Worker 강제 종료 | 다음 실행에서 미완료 시도를 INTERRUPTED로 기록하고 작업 재개 |
| 입력 손상·SQL 불일치 | 해당 작업 FAILED, 결과 트랜잭션 rollback, 다른 정상 작업 계속 |
| DB 쓰기 장애 | Worker 중단, 다음 실행에서 미완료 작업 복구 |
| 보고서 쓰기 장애 | 완료 결과를 재사용해 보고서만 다시 생성 |
| 코드·Python/SQLite 버전·동일 배치의 입력 변경 | 기존 배치 재사용 차단, 새 배치 ID로 등록 |

등록 시 Manifest와 입력 해시가 맞지 않으면 등록을 거부한다. telemetry와 metadata는 실제 파싱할 byte의 SHA-256을 확인하므로 검사 직후 파일이 교체돼도 다른 byte를 성공 결과로 저장하지 않는다. `retry` 전에는 원 파일의 동결 byte를 복구한다. `status`는 Worker 실행 중에도 읽을 수 있고, `report`는 Worker 종료 후 실행한다.

`<state-dir>/reports/<batch_id>/operations.json`과 `.md`에는 단계별 오류·재시도·처리시간·분모를 기록한다. 모든 작업이 성공하면 같은 디렉터리에 `review-queue.md`와 보고서 해시를 가진 `manifest.json`을 발행한다. 마지막 Manifest와 보고서 해시의 일치가 발행 성공 기준이다. `status --json`의 `code_sha256`으로 해당 배치의 구현 버전을 확인한다. 종료 코드는 성공 0, 미완료 배치 1, 입력/상태 오류 2이며 오류는 원문 없는 JSON으로 출력한다.

DB 파일은 `<state-dir>/ops.sqlite3`다. 읽기 전용으로 연결한 뒤 `review_signal`의 R2 신호에서 조회할 `job_id`와 `player_key`를 얻는다. R2 비후보까지 조회하려면 `player_match`를 사용한다. 공격·피해 근거 테이블 `combat_event`의 `event_index`는 Bronze JSON 배열의 0부터 시작하는 위치다. 원 이름과 계정 ID는 저장하지 않으며, R2 공격 ID 연결은 `EXISTS`로 처리해 반복된 공격 ID가 피해 건수를 증폭시키지 않는다.

```sql
SELECT job_id, player_key, rule
FROM review_signal
WHERE rule = 'R2_hit_ratio'
ORDER BY job_id, player_key, rule;

-- 위 결과의 job_id와 player_key를 매개변수로 지정한다.
SELECT event_index, event_type, attack_id, damage, event_time
FROM combat_event
WHERE job_id = :job_id AND player_key = :player_key
ORDER BY event_index;
```

부하는 새 DB를 매번 만들어 준비 실행 1회와 측정 3회를 수행한다. 기본 입력은 고정 seed의
100만·1,000만 이벤트이며, 합성 workload는 매치당 최대 4만 이벤트·100명이다.

```bash
python -m src.ops_demo --output ~/.local/state/pubg-telemetry-watch/benchmark
# 동결 실 데이터 측정도 추가할 때
python -m src.ops_demo --output ~/.local/state/pubg-telemetry-watch/benchmark \
  --real-manifest data/manifests/v1.json \
  --real-manifest data/manifests/v2.json \
  --real-manifest data/manifests/v3/v3-20260901-r2.json
```

측정 파일은 출력 디렉터리의 `measurements.json`이다. 입력 압축 여부·byte·이벤트 수, 처리·보고서 시간, 룰 protocol, SQL query plan, 코드·입력·결과 해시를 기록한다. `EXPLAIN QUERY PLAN`은 배치 protocol의 매개변수로 수집하며, [SQLite가 제공하는 계획 설명](https://www.sqlite.org/eqp.html)이지 인덱스의 성능 기여를 측정한 값은 아니다.

현재 하니스는 GNU Time으로 run과 report 각각 프로세스 종료까지의 peak RSS를 KiB로 기록한다. 기존 `metrics.process_peak_rss_kib`는 커밋 전 [Linux /proc VmHWM](https://docs.kernel.org/filesystems/proc.html)으로 구분해 보존한다. 처리량은 새 성공 이벤트 수 / run+report 초다. 성공 지연은 처리 시작부터 성공 커밋 직후까지며, 후속 계측 저장 전에 종료되면 NULL과 표본 수 감소로 남긴다. 완료 결과 재사용은 새 처리량으로 세지 않는다. 아래 2026-09 기록은 당시 부분 RSS 측정이다. 계약은 [DESIGN §12](DESIGN.md#12-로컬-배치-운영-계약), 현재 재현 절차는 [운영 runbook](docs/operations-runbook.md)을 따른다.

2026-09-10 공개 회귀 46건을 Python 3.10·3.11·3.12에서 확인했다. 실제 자식 프로세스 종료로 요청 예약·작업 시작·결과 커밋 전후의 복구를 검사한다. SQL NULL, 손상 입력과 검사 직후 파일 교체, DB/보고서 쓰기 실패, 중복 등록, runtime 변경 demo, CLI 오류 형식과 비식별 결과도 검증한다. CI는 Python 3.10·3.12에서 전체 검사와 demo를 실행한다.

같은 수정 코드로 동결 134판·5,053,469개 이벤트와 SQL audit 13/13을 재검증했고 동결 파일 723개 SHA를 유지했다. 합성 1M의 준비 1회·측정 1회 확인에서는 측정 실행 10.18초, 기록 RSS 85,592KiB였다. 이는 아래 1M/10M 3회 비교와 별개인 실행 확인이다. 로컬 기록은 `~/.local/state/pubg-telemetry-watch/sip-20260910/verification.json`과 같은 디렉터리의 `benchmark/measurements.json`에 있다.

아래는 2026-09-09 코드의 보존된 측정 기록이다. 시간은 준비 실행을 제외한 3회의 중앙값, RSS는 그 3회의 시도 기록 중 최댓값이다. `run`은 프로세스 시작부터 Manifest 검증·등록·처리·상태 출력까지 포함하고, `report`는 별도 명령의 시간이다. OS 파일 캐시는 초기화하지 않았다. 2026-09-10 입력 검증 수정 후 코드의 3회 비교값으로 사용하지 않는다.

| 입력 | 매치 / 이벤트 | telemetry byte | run 초 | report 초 | 최대 RSS MiB |
|---|---:|---:|---:|---:|---:|
| 합성 gzip 1M | 25 / 1,000,000 | 10,079,685 | 10.52 | 0.61 | 84.2 |
| 합성 gzip 10M | 250 / 10,000,000 | 100,804,344 | 113.85 | 0.63 | 84.4 |
| 동결 v1 JSON | 3 / 106,792 | 65,237,880 | 3.19 | 0.68 | 173.0 |
| 동결 v2 JSON | 38 / 1,474,468 | 890,134,586 | 41.07 | 0.73 | 440.8 |
| 동결 v3 gzip | 93 / 3,472,209 | 149,764,122 | 58.87 | 0.67 | 260.5 |

환경은 WSL2, Ryzen AI MAX+ 392, 사용 가능한 논리 CPU 24개, 메모리 23.3GiB, Python 3.11.15·SQLite 3.50.4다. 합성 입력과 DB는 Linux 파일시스템, 실 입력은 Windows 공유 마운트(`v9fs`)에 있었다. 측정 당시 구현 해시는 `dfea428f8187f311dc1f6e143dcb32338d330aa7439b9e2bf645a9b73e720387`이다. 로컬 원자료는 `~/.local/state/pubg-telemetry-watch/benchmark-20260909/measurements.json`이며 파일 SHA-256은 `64af6f348df523f4bf5ce89ea9011e4c391c01c5dcbce0719539721b24a3cbf0`다. 실 데이터와 측정 산출물은 저장소에 포함하지 않는다.

입력군별 준비 1회·측정 3회, 총 20회의 결과 해시가 일치했다. 같은 매치 최대 크기에서 총량을 10배 늘릴 때 기록된 RSS는 86,264/86,428KiB였고, 원값으로 계산한 증가율은 0.19%로 목표 20% 이내였다. 매치 JSON 전체와 배치의 작업·시도 목록을 메모리에 올리므로 이 결과는 해당 workload 조건에 한정된다. 이 기록의 SQL 계획은 `legacy=False`로 고정한 설명용 계획이어서 legacy 배치의 실제 실행 근거로 삼지 않는다.

동결 파일 723개는 작업 전 SHA-256과 일치했고 기존 v3 SQL audit도 13/13 통과했다. 동결 134판 전체의 재처리 분모는 기존 v3의 선택된 관측 93건·1차 평가 24명과 구분한다.

## v3 RDF semantic shadow

완료된 v3 run의 의미, 관계와 계보를 기존 Gold 발행 뒤에 교차 표현으로 재검산한다. 기존 Gold와
`data/manifests/v3/<run_id>.json`은 수정하지 않으며 API를 호출하지 않는다.

```bash
python -m src.semantic --run-id v3-20260901-r2
```

```text
semantic: SHADOW_VALIDATED triples=51892 DQ=PASS
```

| 검증 대상 | 실측 결과 |
|---|---:|
| source artifact byte와 SHA-256 | 631 / 631 PASS |
| graph 규모 | player 4,992, team 1,938, match 93, observation 93 |
| SHACL Core와 Meta-SHACL | PASS |
| SPARQL competency query | 6 / 6 PASS |
| 기존 graph parity | observation path 93 / 93, 반복 pair 460, lineage edge 721, cycle 0 |
| 기존 SQL parity | 평가 80건, 1차 player 24명, 1차 REVIEW 후보 0건 |
| 제한 identity 검사 | 원 identity exact token 0, secret marker 0, blank node 0 |
| 재현성 | 정렬 N-Triples SHA-256 재실행 일치, 기존 v3 Manifest SHA-256 유지 |
| 로컬 실행 자원 | 24.20초에서 25.88초, peak RSS 최대 233,204 KB, API 호출 0회 |
| namespace 공개 | web 발행 보류, 당시 기록 `DEFERRED_PRIVATE_REPO` |

산출물은 `data/gold/v3/<run_id>/semantic.nt.gz`, `semantic-validation.json`,
`data/manifests/semantic/v3/<run_id>.json`이며 모두 커밋 대상이 아니다. vocabulary source,
SHACL shape와 CQ 6개는 [`docs/ontology`](docs/ontology)에 있다. namespace는 GitHub Pages용
`https://procloudkim.github.io/pubg-telemetry-watch/ontology/pubg-watch.ttl#`로 고정했다.
IRI와 source 고정은 완료됐다. 2026-09-10 [GitHub 저장소](https://github.com/procloudkim/pubg-telemetry-watch)와 API에서 public(`private=false`)을 확인했다. 당시 `DEFERRED_PRIVATE_REPO` 기록의 비공개 전제는 잘못됐다. namespace web 발행은 여전히 보류 중이며, 재개 결정 뒤 Pages 설정, URL과 content type을 검증한다. [저장소 공개와 Pages 발행 설정](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)은 별개다.

이 결과가 보증하는 범위는 semantic schema, lineage, 기존 Python 및 SQL 결과와의 정합성이다.
독립 참조가 없으므로 REVIEW 정확도, 전체 모집단 성능과 외부 일반화는 보증하지 않는다.
원 identity exact token 검사는 문자열 그대로의 노출만 확인하며 변형된 식별자와 재식별 위험 전체를
검증하지 않는다.

2026-09-05 재검증에서 Manifest에 기록된 Python 3.12.3 환경은 semantic 전체 bundle을 같은 byte로
재사용해 PASS했다. Python 3.11.15 환경은 graph와 validation hash를 유지했지만 runtime provenance가
달라 semantic Manifest write-once에서 exit 2로 중단됐다. 전체 bundle 재검증은 기록된 runtime을 요구한다.
설계와 결정은 [`온톨로지 적용 연구`](docs/research/ontology-production-framework.md)와
[`ADR 016`](docs/adr/016-v3-semantic-shadow-sidecar.md)에 있다.

## 독립 참조 first-nail

추가 API 수집 전에 현 룰과 무관한 동일 player-match 참조 양성 20건·음성 20건을 요구했다.
기존 v3 player 응답 200행(고유 105명)과 공식·연구 원천을 감사했지만 계정 현재 상태를 특정
match의 판독과 연결할 시각·match ID가 없어 엄격 적격 수는 0/20·0/20이었다. 따라서
`STOPPED_NO_MATCH_LEVEL_REFERENCE`를 발동했고 이번 단계의 API 호출은 0회, 평가 코드는 만들지 않았다.
분모가 0이므로 혼동행렬과 정확 이항구간도 산출하지 않았다.

40건 균형 표본이 확보되더라도 혼동행렬과 민감도·특이도의 양측 95% Clopper–Pearson 구간만
계산한다. 표본의 양성 비율을 50%로 고정했으므로 모집단 정확도·예측도·발생률이나 전체 서비스
일반화는 추정하지 않는다. 계약·기각한 원천·재개 조건은
[`PLANNING.md` §8.5](PLANNING.md#85-외부-일반화-전-독립-참조-first-nail)와
[`ADR 012`](docs/adr/012-independent-match-reference-first-nail.md)에 있다.

## 데이터 품질 결과

```bash
python -m src.medallion --versions v1 v2
```

2026-09-02 현재 v1은 artifacts 8개·ERROR 0·WARN 1, v2는 artifacts 78개·ERROR 0·WARN 2,
v3는 artifacts 631개·ERROR 0·WARN 2·DQ PASS다.
버전별 WARN 1건은 과거 실행에서 API JSON 전송 원문을 저장하지 않았다는 이력이고, v2의 추가
WARN은 실제 R2 평가 분모 미기록이다. 존재하는
telemetry와 parsed 결과는 38판 모두 event count가 일치했고 checksum·lineage를 manifest에
기록했다. 정본은 `data/manifests/v1.json`, `v2.json`이며 `data/`는 커밋하지 않는다.

## 영속 검토와 운영 재현

schema v2의 검토 CLI는 `review list/show/start/note/complete/reopen`을 제공한다.
상태·메모·이력을 SQLite에 보존하며, 업무 완료 상태와 탐지 판정 REVIEW는 별개다.
이전 schema는 자동 변환하지 않고 거부한다. 새 state 디렉터리로 시작한다.

[실행 절차](docs/operations-runbook.md), [32회 측정과 복구 검증](docs/operations-validation.md),
[편집 가능한 도식·SVG·PDF](docs/architecture/operations.md),
[SQL 소유권·계약·전수 목록](docs/sql/README.md), [보안 경계](docs/security/operations.md)를 참조한다.
GCP staging·원격 CI는 미완료이며 blocker와 미실행 대안을 기록했다.
실행 코드는 [domain/application/adapters/cli](docs/architecture/clean-architecture.md)로 분리했다.
기존 명령·schema v2·REVIEW 계약은 유지하며 [리팩터링 검증](docs/maintenance/refactoring-validation.md)에서
현재 회귀·성능·호환 결과와 미검증 범위를 확인한다.

## 알려진 한계

- R1은 차량만 제외하며 낙하산·리바이브 이동은 아직 구분하지 않는다.
- v1 3판, v2 적격 관측 30건은 작은 표본이라 일반화할 수 없다.
- v2는 `pc-as` 단일 지역·현재 시즌 top10이며 최근 38판의 모드가 혼합돼 지역·시즌·모드·생존시간 편향이 남는다.
- R2는 유효 `damage_events/attacks` 프록시라 한 공격의 다중 피해를 구분한 고유 명중률이 아니다.
- R3는 DBNO groggy 이벤트가 누락되면 해당 kill을 행동 시간창에서 제외하므로 불완전 telemetry에서 미탐 가능성이 있다.
- AI 유형은 제외하지 않고 층화만 하므로 표본 구성에 따른 후보율 차이는 별도 해석이 필요하다.
- 공격 30회 미만과 평가 가능 풀 11명 미만 플레이어-매치는 R2 평가 분모에서 제외된다.
- 과거 v2 산출물은 실제 R2 평가 완료·스킵 분모를 기록하지 않아 후보율을 소급 계산할 수 없다.
- v3는 `pc-as` 한 지역·한 season의 top100 내부 holdout이며 player 중복 가능성 때문에 외부 검증이 아니다.
- v3는 최근 5개를 먼저 고정한 뒤 모드를 필터해 425개 중 332개가 제외됐고, 결과적으로 24명·80건만 평가돼 사전 표본 기준을 달성하지 못했다.
- v3의 prior 제외 39건은 순위 1~10에 전부 집중됐고 보충을 금지해, top100 코호트와 실제 평가 표본이 다르다.
- 같은 플레이어의 반복 match와 24개 cluster만 남아 v3 2차 구간·bootstrap은 제한적이다.
- 동일 player-match의 독립 참조 양성·음성 표본을 확보하지 못해 현 결과로 정확도나 일반화를 주장할 수 없다.
- 과거 v1/v2는 압축 전송 byte와 API JSON 원문을 소급 복원할 수 없다. 새 수집부터만 완전 보존된다.
- semantic sidecar는 완료된 protocol 2의 shadow 검증만 마쳤으며 신규 Gold의 발행 gate가 아니다.
- 저장소는 public이지만 namespace web 발행은 보류 중이며 재개 결정 뒤 별도 검증한다. 과거 `DEFERRED_PRIVATE_REPO` 기록은 현재 저장소 공개 범위를 뜻하지 않는다.

## 정직 경계

1. 신호는 검토 후보이며 오탐을 전제로 사람이 최종 확인한다.
2. 룰은 통계 기준선 수준이며 ML·안티치트 실무를 주장하지 않는다.
3. 공개 API 범위의 데이터만 사용한다. 표본은 공개 sample 매치 3판과 pc-as 리더보드 상위 플레이어의 최근 매치이며, 본인 계정 매치는 포함하지 않았다.

## 데이터 출처와 상표 고지

데이터 출처는 [PUBG Developer API](https://documentation.pubg.com/)와 telemetry CDN이다. 이 공개
저장소는 원시 telemetry·match 데이터를 포함하거나 독립 배포하지 않는다. 상표 고지는
[PUBG Developer Terms of Use](https://developer.pubg.com/tos)를 따른다.

> PUBG, PLAYERUNKNOWN’S BATTLEGROUNDS and all related logos are trademarks of PUBG Corporation or its affiliates.
