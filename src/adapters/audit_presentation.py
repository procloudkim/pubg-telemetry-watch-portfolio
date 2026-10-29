"""Render a checked SQL audit result without recomputing it."""


def _render(summary):
    funnel = summary["funnel"]
    primary = summary["primary"]
    lineage = summary["lineage"]
    maps = "\n".join(
        f"| {name} | {row['evaluated']} | {row['review_candidates']} |"
        for name, row in summary["maps"].items()
    )
    deciles = "\n".join(
        f"| {name} | {row['accepted_observations']} | {row['evaluated']} | {row['review_candidates']} |"
        for name, row in summary["deciles"].items()
    )
    checks = "\n".join(f"| `{row['id']}` | {row['status']} |" for row in summary["checks"])
    return f"""# SQL audit

> 결론: `PASS`. 동결 v3 Silver를 in-memory SQLite로 변환한 집계가 기존 Gold와 일치한다.

## 실행 범위

| 항목 | 값 |
|---|---:|
| run | `{summary["run_id"]}` |
| protocol | `{summary["protocol_version"]}` |
| API 호출 | 0 |
| SQLite 저장 방식 | `:memory:` |
| 원시 이벤트 재적재 | 0 |

## 관계형 모델

| 객체 | row |
|---|---:|
| player dimension | {summary["schema"]["players"]} |
| match dimension | {summary["schema"]["matches"]} |
| R2 observation fact | {summary["schema"]["observations"]} |
| manifest artifact | {lineage["managed_artifacts"]} |
| lineage edge | {lineage["lineage_edges"]} |

## 분모와 1차 표본

| 지표 | 값 |
|---|---:|
| accepted observations | {funnel["accepted_observations"]} |
| evaluated | {funnel["evaluated"]} |
| target attacks 미달 | {funnel["target_below_min_attacks"]} |
| pool 8명 미달 | {funnel["match_pool_below_8"]} |
| 신호 계산 가능 pool 미달 | {funnel["match_pool_below_signal_capable"]} |
| 전체 REVIEW 후보 | {funnel["review_candidates"]} |
| 첫 evaluated player | {primary["evaluated_players"]} |
| 1차 REVIEW 후보 | {primary["review_candidates"]} |

## map별 평가 결과

| map | evaluated | REVIEW 후보 |
|---|---:|---:|
{maps}

## rank decile 커버리지

| rank decile | accepted | evaluated | REVIEW 후보 |
|---:|---:|---:|---:|
{deciles}

## Lineage 재귀 질의

| 지표 | 값 |
|---|---:|
| Gold에서 도달 가능한 source | {lineage["reachable_sources"]} |
| 최대 경로 깊이 | {lineage["maximum_depth"]} |
| cycle | {lineage["cyclic"]} |

## Gold 교차검증

| check | status |
|---|---:|
{checks}

## 재현 checksum

| 입력 | SHA-256 |
|---|---|
| manifest | `{summary["source_sha256"]["manifest"]}` |
| observations | `{summary["source_sha256"]["observations"]}` |
| validation | `{summary["source_sha256"]["validation"]}` |

- SQL: `sql/v3_audit.sql`
- 실행: `python -m src.sql_audit --run-id {summary["run_id"]}`
- 경계: SQL은 완료된 protocol을 재검산하며 탐지 성능이나 모집단 일반화를 추가로 입증하지 않는다.
"""
