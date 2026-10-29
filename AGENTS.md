# AGENTS.md — PUBG Telemetry Watch 에이전트 규약

> **인간은 불변 경계와 검증 지표를 정하고, 에이전트는 그 안에서 자유롭다.**
> 이 문서는 이 저장소에서 작업하는 모든 LLM 에이전트의 단일 지시서다. 도구 무관(Claude, Codex, 기타).

## 0. 철학 (출처와 이 레포에서의 대응)

- **LLM 지식 계층** (Karpathy LLM Wiki 패턴, [gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)):
  원본은 불변, 정리 계층은 LLM 소유, 스키마는 인간과 공동 진화.
  이 레포의 대응: 아래 소유권 맵의 불변/자유/승인 3계층.
- **에이전트 실험 루프** ([karpathy/autoresearch](https://github.com/karpathy/autoresearch)의 구조 차용, 도구 사용 아님):
  수정 금지 파일, 에이전트 편집 파일, 인간 지시서의 3분할과
  **단일 검증 지표를 통과한 변경만 채택하는 루프.** 이 레포의 지표는 §2 회귀 게이트다.

## 1. 소유권 맵

| 계층 | 대상 | 규칙 |
|---|---|---|
| 불변 | PLANNING.md §5 정직 경계 3조, DESIGN.md §4 룰 표의 "근거" 열 | 읽기만 한다. 수정 제안도 하지 않는다 |
| 승인 필요 | 탐지 룰 추가/삭제, 임계값 변경, 의존성 추가, 리포트 판정 어휘, 문서 구조 변경 | 인간(저장소 관리자) 승인 후에만. 승인 전에는 PLAN.md에 제안을 append |
| 자유 | 구현 세부, 리팩터, 테스트 추가, 오탈자, 성능 개선 | 에이전트 재량. 단 §2 게이트 통과 후 커밋 |

## 2. 회귀 게이트 (모든 변경의 채택 기준)

`data/TESTMATCH.telemetry.json` 합성 매치에 대해 parse → detect → report 실행 시:

| 플레이어 | 기대 결과 |
|---|---|
| fast_B (도보 20m/s) | R1_speed 신호 정확히 1건 |
| burst_D (12초 내 3킬) | R3_kill_burst 신호 정확히 1건 |
| driver_C (차량 25m/s) | 신호 0건 (차량 필터 검증) |
| normal_A (도보 4m/s) | 신호 0건 |

이 기대값이 깨지는 변경은 채택하지 않는다. 룰을 바꿔 기대값이 정당하게 달라지면, 승인을 받고 이 표를 같은 커밋에서 갱신한다.

## 3. 금지 목록

- "치터, 위반, 밴" 어휘. 판정은 항상 REVIEW뿐이다
- ML 모델 추가 (PLANNING §4 비범위. 통계 룰이 이 프로젝트의 정직성 설계다)
- API 키를 코드, 커밋, 로그, 채팅에 남기기 (.env만, .gitignore 등록됨)
- `data/`, `reports/` 산출물 커밋
- 실플레이어 닉네임을 README, 리포트 예시, 커밋 메시지에 노출 (예시는 마스킹: `pla***`)
- 대상별 전달 서술과 전달 자료를 Git 추적 경로에 두기 (`private/` 로컬 경로만 사용)

## 4. 프로세스

1. 작업 시작 전 PLANNING.md → DESIGN.md → PLAN.md 순으로 끝까지 읽는다
2. source-of-truth 우선순위: **PLANNING(의도) > DESIGN(계약) > PLAN(상태) > 코드.** 충돌하면 상위 문서가 맞고, 코드를 고친다
3. 코드를 바꾸면 DESIGN.md의 해당 표를 같은 커밋에서 갱신한다 (코드-문서 불일치 금지)
4. 애매하면 추측하지 않는다. PLAN.md 하단에 질문을 append하고 그 작업은 멈춘다
5. 세션 종료 시: PLAN.md 체크박스 갱신 + LOG.md에 한 줄 append. 이것이 다음 세션으로의 handoff다
6. 결정 단위 기록: 임계값 변경, 룰 추가, 구조 변경 시 `docs/adr/NNN-제목.md` 1건
   (형식: Why 문제 / What 결정 / How 구현 / 기각한 대안과 trade-off. MECE하게, 10줄 이내)

## 5. 작업 로그 (LOG.md, append-only)

형식: `YYYY-MM-DD | 에이전트 | 한 일 한 줄 | 게이트 통과 여부`
지우거나 고쳐 쓰지 않는다. 인간의 학습과 추적을 위한 원자료다.

반영 내역: gist는 내장 요약+출처, autoresearch는 "구조 차용" 문구로 정확화, PROCESS.md는 §4로 흡수, why-what-how+trade-off는 결정 단위 ADR(§4-6), Graphify는 합의대로 제외. 닉네임 마스킹 규칙 포함. LOG.md와 docs/adr/ 폴더는 인수 LLM이 첫 세션에 만들면 된다.

## Agent skills

### Issue tracker

작업 이슈는 Git 비추적 `.scratch/<feature>/`의 로컬 Markdown으로 관리한다. [이슈 규약](docs/agents/issue-tracker.md)을 따른다.

### Triage labels

다섯 기본 triage 상태를 사용한다. [상태 대응표](docs/agents/triage-labels.md)를 따른다.

### Domain docs

단일 context의 `GLOSSARY.md`와 기존 `docs/adr/`를 사용한다. [도메인 문서 읽기 규약](docs/agents/domain.md)을 따른다.
