# ADR 006 — v3 top100 내부 holdout protocol 2
- Why: 40/60에서 1차 최소 59명은 스킵·공유 match가 하나만 생겨도 완료할 수 없었다.
- What: v2를 탐색 단계로 두고 v3 top100 전원을 현 룰의 내부 holdout으로 사용한다.
- How: API 최근 5개를 먼저 고정하고 v1/v2 match를 보충 없이 제외해 교집합 0을 DQ로 검사한다.
- How: 순위 10분위·맵·풀 크기 subgroup과 1차 59명·2차 150건 기준은 유지한다.
- Boundary: 같은 지역·시즌이고 player 중복 가능성이 있어 외부 타당성은 주장하지 않는다.
- Decision: `v3-r2-top100-2`로 동결하고 임계값은 변경하지 않는다.
- Trade-off: 최대 1차 분모는 100명으로 늘지만 외부 검증에는 새 시즌·지역·시점이 필요하다.
- Rejected: 40/60 유지, 완료 기준 하향, 결과를 본 뒤 최근 match를 보충하는 방식.
- Evidence: 실 snapshot은 후보 425개이며 prior reference 39개를 제외해 protocol의 필요성을 확인했다.
