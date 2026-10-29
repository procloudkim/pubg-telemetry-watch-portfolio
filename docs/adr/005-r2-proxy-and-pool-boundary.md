# ADR 005 — R2 프록시와 평가 가능 풀
- Why: R2 분자는 고유 명중이 아닌 damage event 수이고 작은 풀의 구조적 0이 분모를 왜곡했다.
- What: 레거시 ID는 유지하되 값을 `damage_events/attacks` 프록시로 명시한다.
- How: 대상 포함 모집단 z-score 최대값 `sqrt(n-1)`에 따라 `z>3.0` 평가 최소 풀을 11명으로 둔다.
- How: 8명 미만과 8~10명을 별도 스킵 상태로 기록하고 후보율은 `evaluated`만 분모로 쓴다.
- Decision: `Z_HIT=3.0`과 탐지 룰 ID·출력은 바꾸지 않는다.
- Trade-off: 과거 v2의 실제 평가 분모는 원자료에 없어 복원하지 않고 WARN으로 남긴다.
- Rejected: `attackId` 연결 새 지표는 별도 룰 승인과 구성타당성 실험이 필요해 이번 변경에서 제외한다.
