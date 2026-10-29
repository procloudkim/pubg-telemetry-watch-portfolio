# ADR 009 — v1 REVIEW 사람 판독
- Why: v1 7건(R2 2·R3 5)의 실제 문맥과 오탐 원인을 원시 이벤트로 확인해야 했다.
- What: R2 두 건은 피해량 0·`Damage_DBNO`가 35/39·108/115를 차지한 분자 왜곡으로 판독했다.
- What: R3 다섯 건은 모두 DBNO 정산을 포함했고, 세 건은 `type=user_ai`; 한 건은 3명이 같은 시각 정산됐다.
- How: Bronze의 attackId·damage·category·dBNOMaker·finisher·groggy 시각·team/type을 Gold별 교차대조했다.
- How: [공식 이벤트 계약](https://documentation.pubg.com/en/telemetry-events.html)은 damage를 실제 체력 감소량으로 정의하고 KillV2의 DBNO·finisher를 분리한다.
- Result: R2 두 건은 방법론적 오탐; R3 다섯 건은 정상 메커니즘으로 설명 가능하나 판정은 모두 `REVIEW`로 유지한다.
- Rejected: 승인 전 DBNO 제외, groggy 시각 전환, AI 층화, 자동 리포트 재분류.
- Trade-off: 재현성을 지키는 대신 큐 정밀도 개선은 승인 후 별도 protocol로 넘긴다.
