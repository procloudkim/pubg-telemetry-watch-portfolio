# Medallion 데이터 파이프라인 계약

## Why — 원시성·정합성·재현성을 함께 지키는 이유

기존 v1/v2 산출물은 `data/` 한 디렉터리에 원시 telemetry, 파싱 결과, 집계가 섞여 있었다.
파이프라인은 동작했지만 어떤 파일이 원본인지, 무엇에서 파생됐는지, 중단 후 파일이 완전한지
기계적으로 증명하기 어려웠다. v3의 독립 검증은 데이터 선택과 분모를 재현해야 하므로 계층,
lineage, checksum, 품질 게이트를 한 계약으로 고정한다.

이 설계는 Databricks가 설명하는 Bronze(raw) → Silver(validated) → Gold(consumer-ready) 구분을
파일 기반 소규모 프로젝트에 맞게 축소 적용한다. 일반 파일시스템에 lakehouse의 트랜잭션 보장을
주장하지 않으며, 같은 디렉터리 임시 파일의 atomic replace와 SHA-256으로 범위를 명시한다.

## What — 계층과 소유권

```text
data/
├─ bronze/{v1,v2,v3/<run_id>}/  수신 원문, write-once
├─ silver/{v1,v2,v3/<run_id>}/  검증·정규화 파생 데이터(v3는 비식별)
├─ gold/{v1,v2,v3/<run_id>}/    신호·기준선·통계 결과
└─ manifests/                   artifact checksum·lineage·DQ 결과
```

| 계층 | 허용 데이터 | 금지되는 처리 | 대표 산출물 |
|---|---|---|---|
| Bronze | API JSON payload, match metadata, telemetry 전송 원문 | 정규화, 값 보정, 이름 제거 | `.json`, `.json.gz`, 호출 원장 |
| Silver | 파싱 집계, 동결 cohort, 수집 preflight, v3 비식별 관측, 상태 분모 | 통계 결론, 원문 덮어쓰기 | parsed match, preflight, observations |
| Gold | 검토 신호, v2 기준선, v3 구간·결론 | 원 ID·닉네임 노출 | signals, validation result |
| Manifest | 모든 artifact의 byte hash·크기·건수·lineage·DQ | 원문 내용 복제 | version/run JSON |

Bronze는 경로가 이미 있으면 byte가 같은지 확인하고 다르면 즉시 중단한다. Silver와 Gold는 입력
checksum과 protocol이 같을 때 재생성할 수 있으며 임시 파일을 완전히 쓴 뒤 `os.replace`한다.
원시 파일은 정리 작업의 대상이 아니며 자동 삭제 기능을 두지 않는다.

DQ PASS 이후의 SQL audit은 계층을 추가하지 않는 읽기 전용 consumer다. 완료된 v3 Silver
observation, Gold validation과 manifest를 `sqlite3 :memory:`에 투영하고 기존 Gold 집계를
교차검증한다. DB 파일, 새 Gold와 원시 이벤트 복제본을 만들지 않는다.

승인된 로컬 배치 경로는 별도 실행 디렉터리의 SQLite에 작업 이력과 비식별 이벤트·결과를 저장한다.
Bronze와 동결 연구 계층은 입력으로만 읽고, 성공 상태와 결과를 DB의 한 트랜잭션으로 커밋한다.
telemetry와 metadata는 실제 파싱할 byte를 읽어 SHA-256을 확인한다. 보고서는 완료 DB 결과에서 재생성한다. 상세 계약은 [DESIGN §12](../../DESIGN.md#12-로컬-배치-운영-계약)와 [ADR 018](../adr/018-local-batch-operations.md)이다.

### 기존 데이터 이관 경계

2026-09-01 v1/v2 telemetry는 수집 때 gzip을 해제한 JSON만 남겼다. 이 파일을 새 Bronze 경로에
hardlink(불가하면 copy)하고 `source_encoding=legacy_decoded_json`으로 기록한다. 존재하지 않는
과거 압축 byte를 재구성했다고 주장하지 않는다. 새 수집부터는 수신 `.json.gz`와 해제 여부를
모두 기록한다. 기존 평면 파일은 검수 호환을 위해 삭제하지 않는다.

## How — manifest와 품질 게이트

### Manifest 최소 스키마

```json
{
  "schema_version": 1,
  "dataset_version": "v3",
  "run_id": "season-run",
  "protocol_version": "v3-r2-top100-3",
  "generated_at": "UTC ISO-8601",
  "artifacts": [{
    "layer": "bronze",
    "dataset": "telemetry",
    "path": "data/bronze/...",
    "media_type": "application/json",
    "source_encoding": "gzip",
    "bytes": 123,
    "records": 456,
    "sha256": "...",
    "derived_from": []
  }],
  "quality": {"status": "PASS", "checks": []}
}
```

경로는 저장소 상대 경로다. SHA-256은 파일 byte 기준이며, `records`의 grain은 dataset마다
명시한다. lineage는 W3C PROV의 `wasDerivedFrom` 관계에 대응하는 `derived_from` 경로 목록으로
표현한다. 이 프로젝트에는 별도 graph 저장소가 필요하지 않아 JSON 배열로 충분하다.

### 품질 차원과 차단 규칙

| 차원 | ERROR 조건 | 관측값 |
|---|---|---|
| Completeness | 선택 match의 Bronze/Silver 누락, v3 top100 holdout 미충족 | expected/actual/누락 ID 수 |
| Uniqueness | match, rank, player_key, observation ID 중복 | duplicate count |
| Validity | JSON 손상, 음수 count, 허용되지 않은 상태·split·mode | 잘못된 row count |
| Consistency | parsed `event_count`와 manifest count 불일치, 룰 protocol 혼합, 분모 등식 불일치 | 양쪽 count |
| Referential integrity | signal/observation이 cohort·match를 참조하지 못함 | orphan count |
| Confidentiality | v3 Silver/Gold에 원 player ID 또는 이름 발견 | 발견 count |
| Timeliness | snapshot 구간·생성시각 누락 | WARN 또는 ERROR 명시 |
| API cadence | 세션 60회 초과는 ERROR, 원장 간격 7초 미만은 WARN | 세션 최대 호출·최소 초 |

ERROR가 하나라도 있으면 `quality.status=FAIL`이며 Gold 결과와 검토 리포트를 발행하지 않는다.
WARN은 결과를 막지 않지만 manifest에 남긴다. 성공·실패 모두 check ID, 기대값, 관측값, 설명을
기록해 “검사했다”는 서술 대신 재검산 가능한 증거를 남긴다.
후속 v3의 cohort coverage FAIL은 DQ 발행 게이트 전 실행 가능성 preflight에서 collect를
차단한다. gate 도입 전 완료 run은 원문 정합성 DQ PASS를 유지하되 회고 coverage
FAIL을 WARN과 Silver `preflight.json`으로 분리 보존한다.

### 버전별 lineage

```text
v1: sample/player + match + telemetry → rule-protocol parsed players → R1/R2/R3 signals → review queue
v2: seasons + leaderboard + players + match + telemetry → rule-protocol parsed matches → R2 evaluated/skipped → baseline
v3: frozen API snapshot + rule protocol + v1/v2 selection + prior v3 cohort → cohort preflight → match + telemetry → pseudonymous observations → internal holdout statistics
```

완료된 v2 legacy와 `v3-r2-top100-2`는 당시 parser protocol로 재현하고, 새 실행만
`rules-event-context-2`·`v3-r2-top100-3`을 쓴다. 서로 다른 protocol의 Silver/Gold를 한
manifest나 통계 분모로 합치지 않는다.

v3 호출 원장은 `session_id`, UTC, endpoint, HTTP 상태, cache 여부를 남긴다. 새 기록은 HTTP 전
예약과 요청 종료 후 완료를 `request_id`로 연결하고 미완료 예약도 예산에서 차감한다. 키와 Authorization
header는 어떤 계층에도 쓰지 않는다. 성공 cache가 있으면 네트워크를 건너뛰고, 실패한 endpoint만
다음 실행에서 재시도한다.

### 외부 근거와 적용 범위

- [Databricks Medallion Architecture](https://docs.databricks.com/aws/en/lakehouse/medallion):
  raw/validated/aggregated 계층의 역할만 차용한다.
- [W3C Data Quality Vocabulary](https://www.w3.org/TR/2016/NOTE-vocab-dqv-20160830/):
  품질을 사용 목적에 대한 fitness로 보고 차원·metric·annotation을 manifest에 명시한다.
- [W3C PROV-O](https://www.w3.org/TR/prov-o/): 파생 artifact의 source lineage 표현 근거다.
- [NIST FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final): SHA-256 byte digest의 정의다.

checksum은 파일 변경을 탐지하지만 출처의 진실성이나 저장장치 내구성을 보장하지 않는다. 원격
백업·object lock·분산 트랜잭션은 현재 1인 로컬 실험에 필요하지 않아 범위 밖이며, 다중 작성자나
복구 SLA가 생길 때 추가한다.
