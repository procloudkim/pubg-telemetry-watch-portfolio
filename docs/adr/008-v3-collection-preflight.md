# ADR 008 — v3 수집 preflight
- Why: protocol 2의 prior 제외 39건이 순위 1~10에 집중됐지만 425회 match 호출 전에 차단하지 못했다.
- What: source-reference·단일 귀속 후보가 top100 전원을 덮고 최대 분모가 59명·150건 이상일 때만 collect를 허용한다.
- How: init·`preflight` 명령이 Silver `preflight.json`에 순위 구간별 커버리지를 저장한다.
- How: FAIL은 `ApiSession` 생성 전 중단하고, 기존 완료 run의 회고 FAIL은 DQ WARN으로 보존한다.
- Boundary: mode·R2 적격성 전 필요조건이며 실제 59명·150건을 보장하지 않는다.
- Trade-off: 완주 가능한 부분 표본도 기각하지만 top100 표현과 실제 분모의 괴리를 먼저 차단한다.
- Rejected: 수집 후 커버리지 진단, 완료 기준 하향, 현 run 사후 보충.
