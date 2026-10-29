# ADR 012 — 독립 player-match 참조 first-nail
- Why 문제: 후보율만으로 동결 룰의 정답 대비 성능이나 전체 모집단 일반화를 알 수 없다.
- What 결정: 룰과 무관한 서로 다른 player-match 양성 20·음성 20을 먼저 확보하지 못하면 일반화 계획을 폐기한다.
- How 구현: 출처를 봉인하고 룰·입력 hash를 동결한 뒤 혼동행렬과 민감도·특이도의 양측 95% 정확 이항구간만 계산한다.
- Evidence: 기존 player 응답 200행·고유 105명에는 동일 match 판정 시각이 없어 엄격 적격은 0/20·0/20이었다.
- Evidence: [Player 스키마](https://github.com/pubg/api-documentation-content/blob/master/swagger/en/schemas/player.yml)는 계정 상태와 최근 match를 별도 필드로 제공한다.
- 기각한 대안: 계정 snapshot, 상위권 가정, 이름 일부가 가려진 공지, 타 게임 데이터, 합성 match를 참조 라벨로 쓰지 않는다.
- Trade-off: 현재 정확도 수치는 포기하지만 근거 없는 수집·평가기 구현과 잘못된 일반화 비용을 막는다.
- Outcome: `STOPPED_NO_MATCH_LEVEL_REFERENCE`; 추가 API 0회, 분모 없는 통계·검증기 미구현, 기존 v1~v3는 보존한다.
