# Clean Architecture 리팩터링 검증

로컬 구현과 검증을 완료했다. 이 문서는 [운영 기능 추가 검증](../operations-validation.md)
이후 수행한 별도 리팩터링의 결과다. 이전 수치를 이번 변경의 기준선으로 재사용하지 않았다.
코드 계약은 [설계 §13](../../DESIGN.md#13-실행-코드의-책임-분리), 폴더와 조회 책임은
[아키텍처](../architecture/clean-architecture.md), 결정은 [ADR 022](../adr/022-clean-architecture-boundaries.md)에 있다.

| 항목 | 실제 결과 |
|---|---|
| 작업 기준 | `refactor/clean-architecture`; 시작 소스 109개 hash·dirty 상태·전체 소스 사본 보존 |
| 변경 전 | 보존 사본에서 62 tests·TESTMATCH·demo·SQL coverage, namespace 격리 PASS |
| 변경 후 | Python 3.10.20 / 3.11.15 / 3.12.3 각각 67 tests·TESTMATCH·demo·SQL coverage PASS |
| 오프라인 | 별도 network namespace·loopback만 존재·외부 경로 차단·자식 상속 확인; 실패 skip 없음 |
| 아키텍처 | domain/application/adapters/cli; 안쪽 의존·cycle 부재·core 직접 I/O 거부·중첩 fingerprint 검사 |
| 보안 회귀 | 기존 checksum/동시 writer/DB 오류/출력 검사 + audit symlink 이탈·소비 byte 교체·SQL 식별자 거부 |
| 원자성 | claim 이후·commit 전후 중단; 결과와 case 일괄 반영; 계측 손실은 성공 상태를 되돌리지 않음 |
| 검토·복원 | 메모·완료·reopen·retry/report 기록 보존, 상태/이력 동시 반영, SQLite backup·integrity/FK·report byte PASS |
| 이전 DB 호환 | 변경 전 소스로 만든 schema-v2 DB를 새 코드로 조회·report; 메모/이력·report byte 일치; reopen은 기존 이력에 append |
| 다른 코드 batch | `BATCH_CODE_CHANGED` 거부 확인; 자동 migration·case 병합 없음 |
| 성능 | 전후 각 16회, 총 32회; 같은 입력 manifest SHA·환경·runtime; 같은 버전 hash와 actor 대응 parity PASS |
| SQL | 두 SQL 파일 byte 불변; 20개 계약 MECE 소유; 81 실행 지점·22 helper·117 고유 정적 텍스트 |
| 실행계획 | 실제 benchmark compute plan; 합성 trace 66개 중 서로 다른 선택 실행문 21개 EXPLAIN/QUERY PLAN 보존 |
| 도식 | 편집 가능한 draw.io 20페이지·SVG 20개·HTML·PDF 20페이지; 구조/bounds/escape 검사와 변경 페이지 시각 확인 |
| 동결 보존 | 837개 checksum 일치; PLANNING §5·DESIGN §4 byte 불변; LOG append-only |

[전후 성능 보고서](refactoring-performance.md)에 모든 반복값·p50/p95와 표본 수·처리량·E2E·
RSS·입력/DB 크기·변동 범위·재현 명령을 둔다. 새 인덱스나 탐지 최적화는 적용하지 않았다.
관측 시간/RSS 감소를 리팩터링만의 인과 효과, 실제 서비스 처리 능력 또는 탐지 정확도로 해석하지 않는다.

## 실패 사례와 수정

분리 중 첫 회귀에서 누락된 token/JSON/정규식 import와 파일 port의 `unlink(missing_ok=...)`
인수 불일치가 드러났다. 실제 구현에서 수정했고 기존 기대값을 낮추지 않았다. 장애 주입이
호환 alias에 남아 실패를 놓치지 않도록 DB·파일·시계·HTTP의 실제 구현 경계로 옮겼다.
기존 schema 테스트에서 기계적 치환이 DB 파일명까지 바꾼 문제도 고쳐 원래 파일명으로 검증했다.

PDF 렌더링의 Poppler Type 3 glyph bounding-box 경고는 남았다. PDF 20페이지를 확인하고
변경 도식의 실제 렌더에서 글자·화살표·경계 잘림을 점검했다. 다른 PDF reader의 렌더링은 미검증이다.
동일 도식의 편집 원본과 SVG도 함께 제공한다.

## 재현과 로컬 증거

설치된 가상환경을 활성화한 뒤 실행한다. 셸에 `python` 별칭이 없으면 해당 환경의
`.venv/bin/python`을 명시한다.

```bash
python tools/sql_inventory.py --check
parent_netns=$(readlink /proc/self/ns/net)
unshare --user --map-root-user --net -- python tools/offline_check.py \
  --parent-netns "$parent_netns" --state-dir /tmp/watch-refactor-demo
python tools/operations_walkthrough.py --output /tmp/watch-refactor-walkthrough
python tools/export_architecture.py
```

기존 경로와 충돌하지 않는 새 state/output을 사용한다. 설치 이후의 namespace 격리를 확인할 수
없는 환경에서는 성공 처리하지 않는다. 전체 CLI 시연은 입력 생성 → 측정 → REVIEW 조회 →
메모·완료 → worker 종료 → 재개 → 중복·기록 보존 → backup/복원이다.

원자료는 `private/refactoring/20261027/`에 보존한다. 시작/종료 source·frozen hash, 전후 각
측정 JSON·actor 결과, 세 runtime 로그, 이전 DB 호환, walkthrough와 query plan이 포함된다.
전체 source와 합성 입력·DB 증거 묶음의 checksum·반출/로컬 복원 결과는 그 경로의 `verification.json`이 정본이다.
실제 API 키·.env·실플레이어 원문은 묶음에 넣지 않는다.

## 미검증과 blocker

| 항목 | 사실·영향 | 해소 조건 | 미실행 대안 |
|---|---|---|---|
| GCP M7/M8 | 이전 크레딧·정확한 만료 미확인, Compute API 비활성 blocker 유지; 이번 작업에서 cloud 상태를 재검증하거나 변경하지 않음 | 최신 계정/만료/잔액과 승인 범위·자원 목록 확인 | 해소 후 동일 bundle로 짧은 관측 또는 별도 기간 재현 |
| Cloud 종료/예약 | 기존 전수 목록·외부 실행기·보존·삭제 제약 blocker 유지; 삭제·예약 0회 | 별도 승인된 private 종료 계약의 gate 충족 | 수동 종료 절차를 별도 검토하되 현재 우회 실행하지 않음 |
| 원격 CI | 로컬 matrix와 namespace는 PASS, GitHub Actions 원격 결과 없음 | 기존 commit/push 보류 해제 후 실제 실행 | 검증 bundle을 새 로컬 환경에서 재현 |
| 장기 관측 | GCP에서 72시간 또는 VM 재시작/반출 검증 수행 0시간 | cloud 사전조건 해소와 실제 관측 시간 확보 | 더 짧은 실제 관측 시간을 명시해 기록 |
| 성능 인과성 | 같은 환경의 순차 3회 비교; host/cache/스케줄링 완전 통제 아님 | 별도 교차·반복 실험 설계 | 현재 반복값과 범위로만 보고 |

이 blocker를 우회한 실행은 하지 않았다. 로컬 리팩터링은 해당 cloud 선행 조건과 독립적으로 완료했다.
새 API 수집·UI/전체 replay·다른 게임·새 의존성·schema 변경·commit/push는 수행하지 않았다.
