# ADR 011 — v3 선행 후보 재사용 차단
- Why 문제: 동결 snapshot 재현에서 protocol 3 현 정책이 protocol 2 후보 425/425를 다시 선택했다.
- What 결정: protocol 3은 v1/v2와 모든 이전 v3 동결 후보를 prior exposure로 제외한다.
- How 구현: 이전 cohort를 hash로 동결하고 후보 ID를 최근 5개에서 보충 없이 제외하며 교집합 0을 DQ로 검사한다.
- 기각한 대안: 평가된 80건만 제외하면 345건, 내려받은 93건만 제외하면 332건이 다시 노출된다.
- Trade-off: 같은 시점 표본은 0건까지 줄 수 있으므로 새 snapshot이 preflight를 통과할 때만 수집한다.
- Evidence: 새 snapshot은 prior 466개와 교집합 0, source 31명·owner 30명·후보 119건이었다.
- Outcome: `init` 12회 뒤 preflight 네 조건이 FAIL해 collect 없이 동결했다.
