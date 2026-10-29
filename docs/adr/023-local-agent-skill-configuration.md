# 023 — 로컬 이슈와 에이전트 스킬 설정

- Why: 엔지니어링 스킬이 이슈 위치·triage 상태·도메인 문서 규약을 공통으로 읽어야 한다.
- What: 사용자 확인으로 로컬 Markdown 이슈, 기본 triage 5상태, 단일 context를 사용한다.
- How: `.scratch/`를 Git ignore하고 `docs/agents/`의 세 설정을 기존 `AGENTS.md`에서 연결한다.
- How: 기존 정본 읽기 순서·ADR 번호·10줄 제한·불변 규약을 유지하며 glossary는 필요할 때 생성한다.
- Trade-off: GitHub tracker는 선택하지 않는다. 원격 이슈·라벨 동기화와 commit/push는 수행하지 않는다.
