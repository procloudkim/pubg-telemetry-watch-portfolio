# v3 통계 검증 방법론

> 상태: 이 문서는 완료된 내부 holdout 계약을 보존한다. 외부 일반화 후속은 독립 참조 0/20·0/20로
> 중단됐으며, 새 API 실행보다 [`PLANNING.md` §8.5](../../PLANNING.md#85-외부-일반화-전-독립-참조-first-nail)가 우선한다.

## Why — 무엇을 검증하는가

v2는 top10의 혼합 모드 최근 경기에서 현 R2가 상위권 플레이를 과도하게 `REVIEW`로 보내는지
탐색했다. 그러나 같은 관측으로 기준 분포를 만들고 결과를 기술했으며, 적격·평가·스킵 분모도
완전히 분리하지 못했다. v3의 목적은 숫자 확대가 아니라 다음 네 가지 불확실성을 분리하는 것이다.

1. 모드 차이: 리더보드 모드와 실제 최근 매치 모드가 달랐던 영향
2. 표본 재사용: 기준을 살핀 표본과 평가 표본이 같았던 영향
3. 반복 관측: 같은 플레이어와 공유 매치가 여러 번 등장한 영향
4. 지표 기하: 작은 매치 풀에서 `z>3.0`이 수학적으로 불가능한 관측을 음성으로 센 영향

top100은 독립 정답이 아니라 **정상 상위권 참조군이라는 운영 가정**이다. 사람 판독 전에는
`REVIEW` 후보율만 측정할 수 있고 실제 오탐률을 확정할 수 없다. 이 경계 때문에 v3 완료와 사람
판독을 분리하며, 후자는 실험 종료 뒤 사용자가 요청할 때 수행한다.

## What — 사전 고정 프로토콜

`v3-r2-top100-2`는 구 이벤트 계수 계약으로 완료·동결됐다. v1 사람 판독 뒤 승인된 R2 이벤트
유효성 변경은 기존 holdout에 소급하지 않고 `v3-r2-top100-3`의 새 표본에만 적용한다.

### 1. 코호트와 split

| 항목 | 고정값 |
|---|---|
| 프로토콜 | `v3-r2-top100-3` (`rules-event-context-2`) |
| 모집단 대용 | snapshot 시점 `pc-as` 현재 시즌 `squad-fpp` leaderboard rank 1~100 |
| 순위 구간 | 1~10부터 91~100까지 10개, 각 10명 |
| split | top100 전원 내부 holdout; 순위 구간은 subgroup 보고에만 사용 |
| 최근 매치 | API 반환 순서 앞 5개에서 v1/v2와 모든 이전 v3 동결 후보 제외, 보충·사후 교체 없음 |
| 채택 모드 | match metadata의 `gameMode == squad-fpp` |
| 공유 매치 | 결정론적 hash가 가장 작은 한 플레이어에게만 귀속 |
| 현 룰 | 양수 피해·공격 ID 연결, `MIN_ATTACKS=30`, 평가 가능 풀 11명 이상, `Z_HIT=3.0` |

v2를 개발·탐색 단계로 간주하고 v3 안에서 다시 보정하지 않는다. `player_key` hash 입력은
`protocol_version|season_id|player_id`이며 이름과 경기 결과는 선택에 쓰지 않는다. 기존 v1/v2
selection 및 이전 v3 cohort의 match ID와 SHA-256을 snapshot에 동결하고 새 후보와의 교집합 0을 DQ로 검사한다.
플레이어는 겹칠 수 있고 지역·시즌도 같으므로 이는 외부 검증이 아닌 내부 holdout이다.

### 1.1 수집 실행 가능성 preflight

후속 run은 snapshot 직후, match metadata 수집 전에 `v3-cohort-coverage-1`을 실행한다.
prior 제외 후 reference를 가진 플레이어와 공유 match 단일 귀속 후 후보를 소유한
플레이어가 각각 100명이어야 한다. 이론상 최대 분모도 1차 59명·2차 150건 이상이어야
하며, 순위 구간별 커버리지와 prior 제외 집중도를 `preflight.json`에 기록한다.

FAIL은 인증 호출 세션 생성 전 collect를 차단한다. PASS는 mode·공격 수·풀 필터 전의
필요조건이지 최종 표본 크기를 보장하지 않는다. 이 gate 도입 전 완주한 protocol 2는 회고
FAIL을 통계 해석 WARN으로 보존하고 원문·checksum DQ와 구분한다.

2026-09-02 protocol 3 첫 snapshot은 이전 후보까지 포함한 prior 466개와 교집합 0을 만들었지만,
최근 reference 371건 제외 후 source 31명·owner 30명·후보 119건으로 네 preflight 조건이 모두
FAIL했다. 따라서 12회 `init`에서 멈추고 match·telemetry 수집과 통계 평가는 수행하지 않았다.

### 2. R2 측정값과 평가 가능 풀

R2의 레거시 ID는 `R2_hit_ratio`지만 실제 비율은 양수 피해이면서 같은 대상의 공격 ID와 연결된
`damage_events/attacks`다. 하나의 공격이 여러 피해 이벤트를 만들 수 있어 1을 넘을 수 있으며
고유 명중률로 해석하지 않는다. 대상 자신을 포함한
`n`개 값의 모집단 평균·모집단 표준편차로 z-score를 만들면 한 관측의 가능한 최대 z는
`sqrt(n-1)`이다. 엄격 조건 `z>3.0`에는 `n>=11`이 필요하므로 풀 8~10은 구조적 스킵이다.

### 3. 상태 분류와 분모

모든 동결 match reference는 아래 경로 중 정확히 하나에 속한다.

```text
reference
├─ pending
├─ api_error
├─ mode_excluded
├─ telemetry_pending
└─ ready / squad-fpp
   ├─ target_below_min_attacks
   ├─ match_pool_below_8
   ├─ match_pool_below_signal_capable (8~10)
   ├─ evaluated / no_candidate (11+)
   └─ evaluated / review_candidate (11+)
```

target 식별 실패, JSON 손상, 필수 필드 불일치는 분석 스킵으로 흡수하지 않고 `data_error`로
분리해 Gold 발행을 중단한다. 보고서의 분모는 다음 등식을 만족해야 한다.

```text
frozen_unique_references = pending + api_error + mode_excluded + telemetry_pending + ready
ready = target_below_min_attacks + match_pool_below_8
      + match_pool_below_signal_capable + evaluated
evaluated = no_candidate + review_candidate
```

### 4. 1차·2차 분석

1차 분석은 top100 내부 holdout 플레이어당 API 순서상 첫 `evaluated` 매치 1건이다. 직접적인 플레이어 반복을
제거한 이진 관측에서 후보율과 단측 95% Clopper–Pearson 정확 경계를 계산한다. 운영 기준 5%는
외부 보편값이 아니라 수동 큐 부담을 제한하기 위해 이 프로젝트가 사전 고정한 기준이다.

| 조건 | 통계 결론 | 후속 조치 |
|---|---|---|
| 1차 평가 플레이어 `<59` | 표본 부족 | 조건을 낮추지 않고 새 표본을 수집 |
| `n>=59`이고 정확 상한 `<0.05` | 기준 지지 | 현 임계값 유지 |
| `n>=59`이고 정확 하한 `>=0.05` | 기준 비지지 | 변경 제안만 작성, 현 임계값 유지 |
| 그 밖 | 불확정 | 현 임계값 유지, 새 시즌·지역·시점 표본 지정 |

후보 0건이면 단측 95% 정확 상한은 `1 - 0.05^(1/n)`이다. `n=59`에서 약 4.951%이므로 59명이
최소다. 2차 분석은 holdout의 모든 평가 완료 관측을 쓰며 최소 150건, 누적 권장 300건이다.
양측 95% Wilson 구간, 순위 구간·맵·플레이어별 후보율, 스킵률을 보고한다.

### 5. 반복 관측과 holdout 보호

- 1차 분석: 플레이어당 1건과 공유 매치 단일 귀속으로 직접 중복을 제거한다.
- 2차 분석: 플레이어를 복원추출하고 선택된 플레이어의 모든 관측을 함께 가져오는 고정 seed
  군집 bootstrap 2,000회를 사용한다. 후보 0건이면 구간이 0으로 퇴화한다는 한계를 명시하고
  1차 정확 상한을 우선한다.
- v3에는 calibration이 없다. 승인된 현 룰을 top100 전체에 고정 적용하고 결과를 본 뒤
  같은 표본으로 다시 맞추지 않는다.
- v1/v2 match와 이전 v3 동결 후보는 제외하되 플레이어·시즌·지역 독립성은 주장하지 않는다. protocol 2 뒤 승인된
  변경은 protocol 3의 새 시즌·지역·시점 표본에서만 검증한다.

## How — 계산과 재현성

### 신뢰구간

- 1차: 이항 CDF를 이분 탐색해 단측 Clopper–Pearson 하한·상한을 계산한다. 추가 의존성은 없다.
- 2차: `z=1.959963984540054`인 양측 Wilson score 구간을 계산한다.
- 사용하지 않음: 단순 Wald 구간. 작은 표본과 0 또는 1에 가까운 비율에서 coverage가 불안정하다.
- 후보율은 소수와 `k/n`을 함께 기록하고 모든 스킵은 사유별 원수치로 남긴다.
- 순위 구간·맵별 결과는 탐색적 기술통계다. 여러 subgroup 중 유리한 결과를 1차 결론으로
  승격하지 않으며, 후속 가설 검정이 필요하면 새 protocol에서 비교군과 다중 비교 통제를 고정한다.
- 공격 30회 조건과 평가 가능 풀 조건은 결측이 무작위라는 보장이 없다. 값을 대입하지 않고
  스킵률을 순위 구간별로 함께 보고해 생존시간·플레이스타일 선택 편향을 드러낸다.

### 외부 근거 팩트체크

| 확인한 주장 | 1차 출처 | 이 프로젝트의 적용 |
|---|---|---|
| Wald 구간은 작은 표본에서 불안정하고 Wilson 계열이 낫다 | [Brown, Cai, DasGupta (2001)](https://projecteuclid.org/journals/statistical-science/volume-16/issue-2/Interval-Estimation-for-a-Binomial-Proportion/10.1214/ss/1009213286.pdf), [Newcombe (1998)](https://onlinelibrary.wiley.com/doi/abs/10.1002/%28SICI%291097-0258%2819980430%2917%3A8%3C857%3A%3AAID-SIM777%3E3.0.CO%3B2-E) | 2차 기술 구간에 Wilson 사용 |
| 정확 이항 경계는 극단 count에서도 정의된다 | [Clopper & Pearson (1934)](https://doi.org/10.1093/biomet/26.4.404) | 1차 5% 운영 기준의 보수적 단측 경계 |
| bootstrap은 경험 분포 재표집으로 불확실성을 추정한다 | [Efron (1979)](https://doi.org/10.1214/aos/1176344552) | 플레이어를 cluster로 재표집하는 2차 보조 구간 |
| holdout의 반복 적응 사용은 허위 발견 위험을 높인다 | [Dwork et al. (2015)](https://pubmed.ncbi.nlm.nih.gov/26250683/) | protocol 사전 고정과 변경 후 새 시점 표본 요구 |
| 두 개 이상 비중첩 cluster가 있으면 일반 독립 추론이 맞지 않을 수 있다 | [Cameron, Gelbach, Miller (2011)](https://doi.org/10.1198/jbes.2010.07136) | 공유 매치 단일 귀속, 플레이어 cluster 보조 분석 |

Clopper–Pearson은 보수적 coverage라는 trade-off가 있다. 여기서는 1차 경계가 작은 `n`과 0건을
다루는 운영 중단 규칙이므로 보수성을 선택하고, 효과 크기 기술에는 Wilson을 함께 제공한다.
cluster bootstrap은 100명 이하 규모에서 점근 보증을 대신하지 않으며 민감도 확인용이다.

### API 계약 교차검증

- PUBG 공식 문서는 기본 rate limit을 10 RPM으로 설명하며 `/matches`와 telemetry는 공식 제한에서
  제외한다고 명시한다. 이 저장소는 사용자 실행 계약이 더 엄격하므로 인증 endpoint 전체에
  7초 간격과 세션 60회 상한을 적용한다.
- leaderboard 응답은 현재 top 500까지 제공하므로 rank 1~100만 결정론적으로 자른다.
- player endpoint는 ID를 한 요청에 최대 10개 받을 수 있으므로 top100 snapshot은 10개 batch로
  고정한다. 과거의 “top100 조회만 10분 이상” 추정은 이 계약으로 정정한다.
- telemetry URL은 match asset 관계에서 얻고 CDN 응답은 인증 없이 받을 수 있으며 gzip 원문을
  먼저 Bronze에 저장한 뒤 해제한다.

출처: [PUBG Rate Limits](https://documentation.pubg.com/en/rate-limits.html),
[Leaderboards](https://documentation.pubg.com/en/leaderboards-endpoint.html),
[Getting Started](https://documentation.pubg.com/en/getting-started.html),
[Telemetry](https://documentation.pubg.com/en/telemetry.html).

## 완료와 해석 경계

v3 protocol 3 완료에는 preflight PASS, top100 내부 holdout/모든 prior match 교집합 0/원문 보존/호출 원장/DQ PASS와 함께 1차 59명 및 2차 150건이
모두 필요하다. 통계 결론이 `기준 지지`일 필요는 없다. `기준 비지지`나 `불확정`도 프로토콜대로
도달했다면 유효한 실험 결과다. 완료된 protocol 2와 protocol 3 결과는 결합하지 않는다.
