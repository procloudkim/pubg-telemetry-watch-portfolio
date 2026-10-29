# ADR 013: 관계 graph feasibility spike

- Why 문제: manifest 계보는 JSON으로 충분하지만 93판의 반복 동료 관계와 key 단절은 다중 경로 감사 대상이다.
- What 결정: production 경로를 바꾸지 않고 Silver observation 93판만 stdlib in-memory graph로 투영한다.
- How 구현: roster의 playerId를 기존 cohort hash로 변환하고 player, team, match, observation edge를 만든다.
- How 검증: 반복 pair, observation 연결, manifest DAG를 집계하고 원 identity 출력과 orphan을 차단한다.
- 기각 대안: Neo4j와 persistent graph는 실효성 검증 전 의존성과 운영면을 늘리므로 제외한다.
- Trade-off: graph 원본을 저장하지 않아 대화형 질의는 없지만 동일 입력의 projection hash로 재현성을 검사한다.
