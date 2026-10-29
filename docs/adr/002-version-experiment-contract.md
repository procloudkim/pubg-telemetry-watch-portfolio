# ADR 002 — 버전별 실험 계약 정본
- Why: v1·v2·v3의 목표와 방법이 PLAN·DESIGN·README에 흩어져 상태와 의도가 섞였다.
- What: 목표·표본·지표·성공/중단 조건의 정본을 `PLANNING.md` §8로 통합한다.
- How: DESIGN은 구현, PLAN은 상태, README는 실행 요약만 소유하고 정본을 링크한다.
- Decision: v1은 성립성, v2는 top10 편향 탐색, v3는 top100 독립 재현성 검증이다.
- Decision: v3는 모드 통제와 v1/v2 match 제외 top100 내부 holdout을 필수로 한다(ADR 006).
- Decision: holdout 평가 완료 150건을 최소, 300건을 누적 권장 목표로 둔다.
- Trade-off: 더 강한 독립성을 얻는 대신 여러 API 세션과 캐시·재개 구현이 필요하다.
- Rejected: top100으로 숫자만 늘려 같은 표본에서 보정과 평가를 반복하는 방식.
- Scope: 이번 결정은 문서 구조와 실험 계약만 확정하며 API 실행·룰·임계값은 바꾸지 않는다.
