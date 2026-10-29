# ADR 003 — v3 고정 검증 프로토콜 (ADR 006으로 대체)
- Why: v2의 혼합 모드·표본 재사용·반복 관측 때문에 외부 재현성을 판단할 수 없었다.
- What: top100을 순위 구간별 4/6 calibration·holdout으로 결정론적 분할한다.
- How: 최근 5개, `squad-fpp`만, 공유 match 단일 귀속, 1차 플레이어당 첫 적격 1건을 고정한다.
- Metric: 1차 단측 Clopper–Pearson, 2차 Wilson과 플레이어 군집 bootstrap을 보고한다.
- Decision: 1차 59명·2차 150건을 최소로 하고 5%를 사전 운영 기준으로 둔다.
- Boundary: 사람 판독 전 결과는 정상 참조군 REVIEW 후보율이며 확정 오탐률이 아니다.
- Trade-off: 독립성과 정직성은 높지만 혼합 모드 표본보다 수집량과 스킵이 늘어난다.
- Rejected: 같은 top100으로 보정·재평가하거나 결과를 본 뒤 split·표본 조건을 바꾸는 방식.
- Source: `docs/methodology/v3-statistical-validation.md`의 1차 논문·공식 API 교차검증.
