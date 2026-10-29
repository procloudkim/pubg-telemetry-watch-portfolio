# 022 — 계산·실행·외부 자원·표현의 책임 분리

- Why: CLI·파일·HTTP·SQL과 순수 계산이 결합되어 테스트 주입과 변경 영향 추적이 어렵다.
- What: 사용자 승인으로 domain/application/adapters/cli를 분리하고 기존 명령·데이터 계약을 보존한다.
- How: PUBG 계산은 domain의 전용 모듈, 업무 변경과 조회는 application, SQL·파일·HTTP·RDF·표현은 adapter가 소유한다.
- How: 계층 의존 검사·재귀 소스 fingerprint·격리 회귀·동결 checksum·교차 버전 결과 비교를 채택 gate로 둔다.
- How: 근거→검토/복구 이력→운영 지표 순의 조회 계약을 공유하며 UI·전체 리플레이는 후속 제안으로 둔다.
- Trade-off: schema/룰/의존성/운영 식별자 계산식은 유지하되 코드 hash가 달라진 batch는 기존 계약대로 실행 재개를 거부한다.
- Trade-off: 실제 대체 경계에만 port를 두며 새 API 수집·다른 게임 지원·cloud 실행을 포함하지 않는다.
