# ADR 010 — 이벤트 문맥 룰 protocol 2
- Why: v1 R2는 피해량 0 DBNO 이벤트, R3는 최종 정산 시각 때문에 7건 모두 행동 신호와 어긋났다.
- What: R2 분자는 `damage>0`이며 같은 대상의 `LogPlayerAttack.attackId`와 연결된 이벤트만 센다.
- What: R3는 대상이 만든 DBNO의 groggy 시각과 직접 종료의 KillV2 시각을 행동 시각으로 쓴다.
- What: 피해 대상 `type=user_ai`는 제외하지 않고 `user_ai_only/non_user_ai_only/mixed/unknown`으로 층화한다.
- How: [공식 이벤트 계약](https://documentation.pubg.com/en/telemetry-events.html)의 attackId·damage·DBNO 필드를 파서에서 연결하고 근거에 원 시각을 함께 둔다.
- How: v1은 `rules-event-context-2`, 다음 v3는 `v3-r2-top100-3`; v2 legacy와 완료된 v3 protocol 2는 보존한다.
- Boundary: R1·세 임계값·REVIEW 어휘는 바꾸지 않으며 변경 룰의 유효성은 새 외부 표본 전까지 주장하지 않는다.
- Rejected/Trade-off: AI 제외·기존 결과 덮어쓰기·임계값 조정은 기각; 정밀도 대신 protocol 간 직접 결합은 포기한다.
