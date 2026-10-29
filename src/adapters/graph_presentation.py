"""Presentation of an already verified graph read model."""


def _render(summary):
    relationship = summary["relationship_query"]
    keys = summary["key_query"]
    lineage = summary["lineage_query"]
    graph = summary["graph"]
    source = summary["source"]
    checks = "\n".join(
        f"| `{row['id']}` | {row['observed']} | {row['expected']} | {row['status']} | {row['detail']} |"
        for row in summary["checks"]
    )
    node_rows = "".join(f"| {key} | {value:,} |\n" for key, value in graph["nodes"].items())
    edge_rows = "".join(f"| {key} | {value:,} |\n" for key, value in graph["edges"].items())
    player_type_rows = "".join(
        f"| {key} 형식 player key | {value:,} |\n"
        for key, value in relationship["players_by_key_type"].items()
    )
    repeated_type_rows = "".join(
        f"| {key} 형식 반복 pair | {value:,} |\n"
        for key, value in relationship["repeated_by_key_type"].items()
    )
    if summary["decision"] == "FEASIBLE_FOR_NEO4J_REVIEW":
        head = (
            f"Silver observation {source['selected_matches']}판에서 반복 동료 관계와 key 경로를 "
            "재구성할 수 있다. 관계는 분석 가능성이지 행동 결론이 아니다."
        )
        decision = "관계 graph는 반복 동료와 key 경로 감사에 적용 가능하다."
    else:
        head = "입력 또는 DQ 조건이 충족되지 않아 graph 적용 결론을 보류한다."
        decision = "검증 조건 미충족으로 graph 적용을 중단한다."
    return f"""# 관계 graph feasibility 감사

> 결론: `{summary["decision"]}`. {head}

## 1. 범위와 경계

- run: `{summary["run_id"]}`
- protocol: `{summary["protocol_version"]}`
- API 호출: 0회
- 사용 match: Silver observation {source["selected_matches"]}판
- 제외 match: cached metadata {source["available_match_metadata"] - source["selected_matches"]}판
- 출력: aggregate와 checksum만 기록, graph node와 edge 및 원 identity 미저장

## 2. Graph schema

| source | relation | target | 목적 |
|---|---|---|---|
| Player | MEMBER_OF | TeamInstance | match별 team membership |
| TeamInstance | IN_MATCH | Match | team과 match 연결 |
| Player | OBSERVED_AS | Observation | cohort key 연결 |
| Observation | MEASURED_IN | Match | player-match 경로 검사 |
| Artifact | DERIVED_FROM | Artifact | Bronze, Silver, Gold 계보 |

| node | count |
|---|---:|
{node_rows}| 합계 | {graph["total_nodes"]:,} |

| edge | count |
|---|---:|
{edge_rows}| 합계 | {graph["total_edges"]:,} |

## 3. Query 1, 반복 동료 관계

| 지표 | 값 |
|---|---:|
| player | {relationship["players"]:,} |
{player_type_rows}| team instance | {relationship["teams"]:,} |
| membership | {relationship["memberships"]:,} |
| 고유 teammate pair | {relationship["unique_teammate_pairs"]:,} |
| 2판 이상 반복 pair | {relationship["repeated_at_least_2"]:,} |
{repeated_type_rows}| 3판 이상 반복 pair | {relationship["repeated_at_least_3"]:,} |
| 최대 반복 match | {relationship["maximum_repeat"]:,} |
| observation player와 접점이 있는 반복 pair | {relationship["repeated_touching_observed"]:,} |
| teammate edge가 있는 observation player | {relationship["observed_players_with_teammate"]:,} |

- 해석: match를 넘는 관계 질의가 실제 비어 있지 않다.
- 제한: 반복 관계만으로 REVIEW 근거나 새로운 룰을 만들지 않는다.

## 4. Query 2, key 연결성

| 경로 | 연결 |
|---|---:|
| cohort player에서 선택 graph | {keys["cohort_in_selected_graph"]} / {keys["cohort_players"]} |
| observation 고유 player에서 선택 graph | {keys["observed_in_selected_graph"]} / {keys["observed_unique_players"]} |
| observation row에서 해당 match roster | {keys["observation_rows_in_own_match"]} / {source["observations"]} |
| observation row에서 동결 parsed key 직접 연결 | {keys["parsed_direct_rows"]} / {source["observations"]} |

- 해석: roster-derived seasonal key는 observation을 연결하지만 동결 parsed key namespace는 다르다.
- 제한: graph projection은 동결 Silver를 수정하거나 두 key를 동일 identity로 영구 확정하지 않는다.

## 5. Query 3, lineage

| 지표 | 값 |
|---|---:|
| manifest 관리 artifact | {lineage["managed_artifacts"]:,} |
| 외부 source node | {lineage["external_source_nodes"]:,} |
| lineage edge | {lineage["edges"]:,} |
| Gold에서 도달 가능한 source | {lineage["gold_reachable_sources"]:,} |
| 최대 경로 깊이 | {lineage["maximum_depth"]} |
| cycle | {int(lineage["cyclic"])} |

- 해석: lineage는 graph 질의가 가능하지만 현재 규모에서는 manifest JSON으로 충분하다.

## 6. Data quality

| check | observed | expected | status | 근거 |
|---|---:|---:|---|---|
{checks}

## 7. 재현 checksum

| 입력 또는 projection | SHA-256 |
|---|---|
| cohort | `{source["source_sha256"]["cohort"]}` |
| observations | `{source["source_sha256"]["observations"]}` |
| manifest | `{source["source_sha256"]["manifest"]}` |
| selected match metadata | `{source["source_sha256"]["selected_matches"]}` |
| graph projection | `{graph["projection_sha256"]}` |

## 8. 결정

- `{summary["decision"]}`: {decision}
- Neo4j, persistent graph, Cypher와 graph 기반 신규 룰은 후속 승인 전 범위 밖이다.
- 다음 단계는 이 결과의 적용 가치와 대화형 질의 필요성을 검토하는 별도 결정이다.
"""
