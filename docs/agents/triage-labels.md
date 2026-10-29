# Triage 상태 대응표

GitHub 라벨을 생성하지 않는다. 로컬 triage 이슈의 `Status:` 필드에 아래 값을 사용한다.

| 스킬의 역할 | 로컬 상태 | 의미 |
|---|---|---|
| `needs-triage` | `needs-triage` | 관리자의 분류 필요 |
| `needs-info` | `needs-info` | 추가 정보 대기 |
| `ready-for-agent` | `ready-for-agent` | 명세와 선행 조건이 갖춰져 에이전트 실행 가능 |
| `ready-for-human` | `ready-for-human` | 사람이 수행할 작업 |
| `wontfix` | `wontfix` | 수행하지 않기로 결정 |

상태 이름은 사용자 확인을 받아 변경한다. 대기·차단 항목을 ready로 표시해 선행 조건을 우회하지 않는다.
