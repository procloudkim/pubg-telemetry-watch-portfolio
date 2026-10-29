# 운영 변경의 보안 경계와 검사

이번 범위는 신뢰하는 로컬 운영자가 사용하는 Linux/WSL 단일 worker CLI다. 공개 네트워크 서비스,
다중 사용자 인증, 악의적 OS 관리자 방어를 구현한 것은 아니다. 현재 코드 경계는
[D13](../architecture/D13.svg), 입력과 권한 경계는 [D14](../architecture/D14.svg)에 있다.

| 경계 | 구현·검사 | 남는 한계 |
|---|---|---|
| manifest → 입력 파일 | source root containment, bytes/SHA/records/객체 배열, 실제 소비 byte 재검증; 입력 교체·손상 회귀 | 전체 JSON을 메모리로 읽음; 적대적 압축 팽창·자원 한도는 제공하지 않음 |
| CLI → SQL | 값 바인딩; 동적 열·table/view 이름은 내부 고정 목록; 빈 label/note와 잘못된 전이 거부 | operator는 인증 정보가 아닌 label; OS 계정과 state 경로 권한을 신뢰 |
| 결과 → DB | FK/CHECK/UNIQUE, flock, WAL/FULL, 결과·case·성공 atomic commit | 하드웨어 전원/디스크 장애나 원격 파일시스템 내구성을 검증하지 않음 |
| 사람 기록 → DB | 상태·이력 같은 transaction; append-only trigger; retry/report가 기록을 초기화하지 않음 | DB 소유자는 trigger/DB를 직접 바꿀 수 있어 변조 방지 증명은 아님 |
| DB → 공개 출력 | 원 account/name 적재 제외, REVIEW 어휘, 고정 JSON 오류, 완료 report atomic 발행 | 자유 입력 note는 로컬 JSON으로 반환; 민감정보를 입력하면 보존되므로 익명화 보증 없음 |
| test/demo → 프로세스 | shell=False argv, child network namespace 상속 확인, 외부 경로 차단 | dependency 설치 단계는 네트워크 사용; 원격 CI 자체는 미실행 |
| draw.io → HTML/SVG | 고정 Dnn 파일 ID·bounds·hex color; text escape; embedded SVG 요소/속성 및 정적 색 CSS만 허용 | 범용 draw.io renderer가 아님; 새 도형/스타일은 검토 후 명시적 지원 |
| 시연 → PASS 판정 | assert self-check; Python -O 실행은 결과 생성 전에 거부 | 실제 사람 사용성·침투 테스트는 별도 검증 필요 |

새 도식 exporter 검사는 Google 원본 아이콘의 `<style>`를 처음 거부했다. 원본을 확인하니
단순 class별 `fill: none` 또는 6자리 hex 색이었다. 그 문법만 허용하고 script·event handler·
원격 href·xml:base·style 속성·CSS import/url은 계속 거부하는 테스트를 추가했다.
아이콘 원본과 checksum을 유지했고 보안 검사를 비활성화하지 않았다.

검토한 경로는 src의 SQL/파일/네트워크/subprocess 경계와 이번 tools 변경이다.
`tests/test_ops.py`, `test_ops_review.py`, `test_document_tools.py`, `test_sql_inventory.py`가
손상·경로·DB·종료·도식 입력을 검증한다. fetch/research 경로도 Files·HTTP·Clock 경계로 분리하고 원장 중단·호출 예산·합성 cohort 회귀를
수행했다. 실제 API 수집은 하지 않았다. 저장소 전체 침투 검사나 취약점 없는 코드라는 인증을 수행한 것은 아니다.
credential/.env/원 연구 telemetry는 배포·측정 증거 묶음에 포함하지 않는다.

책임 분리와 검사 지점은 [계층 문서](../architecture/clean-architecture.md), 실행 증거는
[리팩터링 검증](../maintenance/refactoring-validation.md)에 있다. SQL audit는 symlink로 source
root를 벗어나는 경로를 거부하고, 검증 뒤 교체된 파일도 실제 소비 byte의 SHA로 차단한다.
RDF가 다시 읽는 match metadata와 semantic 핵심 JSON에도 소비 byte 검증을 적용한다.
SQL view/group 식별자는 코드의 명시적 허용 목록으로 거부 경계를 검사한다. 이 보강은
schema·탐지 규칙·임계값을 변경하지 않는다.
