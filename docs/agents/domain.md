# Domain docs

기존 정본과 ADR을 도메인 탐색에 사용한다. 이 문서는 기술·DB 선택을 새로 결정하지 않는다.

## 읽기 순서

1. `AGENTS.md`를 확인하고 기존 규약대로 `PLANNING.md` → `DESIGN.md` → `PLAN.md`를 끝까지 읽는다.
2. 루트 `GLOSSARY.md`가 있으면 용어를 읽고, 관련 `docs/adr/`를 확인한다.
3. glossary가 없으면 작업을 계속한다. 이름만 채우기 위해 미리 만들지 않으며, `domain-modeling`에서 실제 용어를 합의할 때 생성한다.

## 단일 context 구조

```text
/
├── GLOSSARY.md       # 실제 용어 합의 시 생성
├── docs/adr/         # 기존 3자리 번호·10줄 이내 규약 유지
└── src/
```

용어가 정의돼 있으면 이슈·제안·테스트에서도 같은 이름을 사용한다. 새 용어가 필요하면 기존 개념과 구별되는지 확인한다.
ADR과 충돌하는 제안은 해당 ADR과 충돌 이유를 먼저 밝힌다. 기존 결정을 조용히 덮어쓰지 않는다.
`PLANNING.md` §5와 `DESIGN.md` §4 근거의 불변 규약, 승인 범위와 동결 연구 보존은 그대로 적용한다.
문서 우선순위는 `PLANNING > DESIGN > PLAN > 코드`다. glossary와 이 설정이 이를 변경하지 않는다.
