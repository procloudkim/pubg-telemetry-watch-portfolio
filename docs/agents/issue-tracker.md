# Issue tracker: Local Markdown

이 저장소의 이슈와 구현 명세는 Git 비추적 `.scratch/`에서 관리한다. GitHub 이슈·라벨은 생성하지 않는다.

## 파일 규약

- 기능마다 `.scratch/<feature-slug>/` 디렉터리를 사용한다.
- 명세는 `spec.md`, 이슈는 `issues/<NN>-<slug>.md`에 한 건씩 저장하며 번호는 `01`부터 시작한다.
- triage 상태는 파일 상단의 `Status:`에 [상태 대응표](triage-labels.md)의 값을 기록한다.
- 대화·진행 기록은 `## Comments` 아래에 append한다.
- 스킬의 “publish to the issue tracker”는 로컬 파일 생성을 뜻한다. “fetch the relevant ticket”는 지정 파일 읽기를 뜻한다.
- 키·인증 파일·실플레이어 원문은 기록하지 않는다. 대상별 전달 자료는 기존 규약대로 `private/`에 두고 필요하면 경로만 연결한다.
- blocker는 보고하고 해당 작업을 멈춘다. 대안은 미실행으로 기록한다. 원격 반영·commit/push 보류를 이 설정으로 해제하지 않는다.

## Wayfinding

- map은 `.scratch/<effort>/map.md`, child ticket은 같은 디렉터리의 `issues/NN-<slug>.md`다.
- child의 `Type:`은 `research`, `prototype`, `grilling`, `task` 중 하나다.
- `Blocked by: NN, NN`에 선행 이슈 번호를 적으며 모두 해결된 뒤 시작한다.
- 미해결·미담당·선행 이슈 없는 항목 중 번호순으로 선택하고, 작업 시작 전 `Status: claimed`를 기록한다.
- 해결하면 `## Answer`에 결과를 append하고 `Status: resolved`로 바꾼 뒤 map의 Decisions-so-far에 근거 경로를 연결한다.
- `claimed`·`resolved`는 wayfinding 실행 상태이며 위 triage 역할 이름을 대체하지 않는다.
