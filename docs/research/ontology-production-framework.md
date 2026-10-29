# 최소 온톨로지 프로덕션 적용 선행 연구

> 헤드 메시지: Neo4j와 영속 graph 저장소를 제외한다. 완료된 v3 Gold 뒤에 파일 기반 RDF shadow sidecar를 두고 RDFLib, SHACL Core, pySHACL, PROV-O와 SPARQL로 의미와 계보를 재검산한다. 동결 run에서 `SHADOW_VALIDATED`를 확보했으며 기존 Gold 발행 gate로 승격하지 않는다.

## 1. 의사결정 요약

| 질문 | 결론 | 근거 |
|---|---|---|
| 온톨로지가 해결할 문제 | Silver 관측, Gold 결과, protocol, match, 팀, artifact 계보의 의미와 연결 계약 | 현재 JSON manifest는 무결성을 검사하지만 관계 의미를 표준 어휘로 발행하지 않음 |
| 온톨로지가 해결하지 않을 문제 | REVIEW 정확도, 모집단 일반화, 독립 참조 부재 | 의미 모델은 라벨과 외부 타당성을 만들지 못함 |
| 형식 | RDF 1.1, RDFS와 최소 OWL 2 선언, SHACL Core, PROV-O, SPARQL 1.1 | W3C 표준 조합, 용도별 책임 분리 |
| Python 실행기 | RDFLib 7.6.0, pySHACL 0.40.1 exact pin | Python 3.12.3에서 parse, SPARQL, 적합과 부적합 및 실 run 검증 완료 |
| 저장 | human authored Turtle, generated blank-node-free N-Triples gzip | git diff 가독성과 byte 재현성 분리 |
| 배치 위치 | 완료된 v3의 post-run Gold shadow | 기존 Gold와 v3 Manifest 불변, 별도 semantic Manifest 발행 |
| 추론 | `inference=none`, 명시 triple만 사용 | 현 competency question에 추론 요구가 없음 |
| 현재 상태 | `SHADOW_VALIDATED`, `NOT_PRODUCTION_GATE` | 51,892 triples, SHACL PASS, CQ 6 / 6 PASS, API 호출 0회 |

## 2. Why | 해결할 문제와 정직 경계

### 2.1 해결할 문제

- Silver의 `player_key`, match, observation, team instance가 어떤 의미와 범위를 갖는지 기계 판독 계약으로 고정한다.
- Gold 결과가 어떤 observation, protocol, artifact에서 파생됐는지 표준 관계로 질의한다.
- 서로 다른 key namespace를 같은 identity로 오인하는 연결을 차단한다.
- 필수 관계, datatype, cardinality, 상태 집합, lineage 방향을 데이터 발행 전에 검증한다.
- ontology version, projector version, protocol version과 입력 checksum을 함께 남겨 재현 단위를 고정한다.

### 2.2 해결하지 않는 문제

- REVIEW 후보를 외부 정답으로 바꾸지 않는다.
- 사람 판독, 독립 player-match 참조, 혼동행렬을 대체하지 않는다.
- R1, R2, R3 룰과 임계값을 추가하거나 변경하지 않는다.
- Bronze 48 event type 전체를 복제하지 않는다.
- 신규 Medallion 계층, 영속 graph DB, API, dashboard를 만들지 않는다.
- 관계 존재만으로 행동 의미를 추론하지 않는다.

### 2.3 도입 전제

- [Stanford Ontology Development 101](https://protege.stanford.edu/publications/ontology_development/ontology101-noy-mcguinness.html)은 domain과 scope를 먼저 정하고 competency question으로 필요한 상세 수준을 제한하며 기존 ontology 재사용을 검토하는 반복 절차를 제안한다.
- [W3C Data on the Web Best Practices](https://www.w3.org/TR/dwbp/#ChooseRightFormalizationLevel)은 데이터와 사용처에 맞는 형식화 수준을 선택하고 표준 vocabulary를 재사용하도록 권고한다.
- 본 설계는 두 원칙을 적용해 현재 감사 질문에 필요한 개념만 포함하고, PROV-O와 XSD를 재사용한다.

## 3. What | 현재 저장소의 증거

| 증거 | 관측값 | 설계 영향 | 출처 |
|---|---:|---|---|
| 대상 run | `v3-20260901-r2` | 완료된 동결 데이터로 shadow 검증 | [`DESIGN §9`](../../DESIGN.md) |
| 관계 투영 규모 | player 4,992개, team 1,938개, observation 93개 | 영속 store 필요성을 입증하지 못하는 규모 | [`DESIGN §9`](../../DESIGN.md) |
| 반복 팀 관계 | 2 match 이상 pair 460개 | 관계 질의는 비어 있지 않음 | [`DESIGN §9`](../../DESIGN.md), [`ADR 013`](../adr/013-graph-feasibility-spike.md) |
| observation과 roster 연결 | 93 / 93 | player, observation, match 경로를 ontology에 포함 | [`DESIGN §9`](../../DESIGN.md) |
| observation과 parsed key 직접 연결 | 0 / 93 | `owl:sameAs` 금지, key namespace 명시 | [`DESIGN §9`](../../DESIGN.md) |
| lineage | edge 721개, cycle 0 | `prov:wasDerivedFrom` 재사용 | [`DESIGN §9`](../../DESIGN.md) |
| graph DQ | 15 / 15 PASS | 현재 Python 검사를 기준선으로 유지 | [`DESIGN §9`](../../DESIGN.md) |
| SQL 교차검증 | evaluated 80건, 1차 player 24명, lineage edge 721개 | SPARQL 결과를 기존 SQL과 parity 검사 | [`ADR 014`](../adr/014-in-memory-sql-audit.md) |
| semantic shadow | 51,892 triples, managed artifact 631개, external artifact 2개 | 파일 graph로 충분하며 별도 store가 필요하지 않음 | `semantic-validation.json`, [`ADR 016`](../adr/016-v3-semantic-shadow-sidecar.md) |
| semantic 품질 | SHACL PASS, CQ 6 / 6 PASS, raw token 0, secret marker 0, blank node 0 | 구조, parity, 제한 identity 검사를 분리해 확인 | `semantic-validation.json` |
| 재현성과 자원 | N-Triples hash 재실행 일치, 24.20초에서 25.88초, peak RSS 최대 233,204 KB | 현 동결 규모에서 memory batch 유지 | semantic Manifest, `/usr/bin/time` 실측 |
| 외부 참조 | 양성 0 / 20, 음성 0 / 20 | 정확도와 일반화 주장을 금지 | [`ADR 012`](../adr/012-independent-match-reference-first-nail.md) |

## 4. How | 조사 방법

- 조사일: 2026-09-04.
- 질문: 현재 Python, 파일 기반 Medallion, 비식별, checksum, atomic write 계약을 유지하면서 의미 모델과 검증을 추가할 최소 조합은 무엇인가.
- 1차 근거: W3C Recommendation, 각 프로젝트 공식 문서, 공식 PyPI metadata, 저장소 동결 산출물.
- 후보 범주: 직접 RDF library, ontology meta-framework, RDF store, JVM semantic platform, property graph DB.
- 평가 기준: 표준 적합성, SHACL 검증, Python 3.10 이상 호환, 파일 실행, 재현성, 보안 경계, 운영면, 기존 코드 재사용.
- 검증 방법: 문서 주장과 공식 원문 대조, 현재 package metadata 대조, Python 3.12.3 격리 smoke, 기존 graph와 SQL 결과 교차대조.
- 제외 기준: 현재 competency question과 연결되지 않는 기능, 영속 서비스, 추론 engine, code generator, 신규 데이터 수집.

## 5. factchk 판정표

판정은 주장 진위와 프로젝트 상태를 분리한다. `PASS`는 근거가 주장을 지지함을 뜻하고, `반증`은
검사용 반대 명제가 근거와 충돌함을 뜻한다. `NOT_EVALUATED`는 측정 근거가 없음을 뜻하며 프로젝트
실패가 아니다. 외부 발행은 보류 중이며 과거 `DEFERRED_PRIVATE_REPO` 값은 현재 저장소 공개 범위를 뜻하지 않는다(§17). `FAIL`은 실행, DQ와
preflight 계약이 실제 조건을 충족하지 못한 경우에만 사용한다.

| ID | 주장 | 판정 | 확인 근거와 교정 |
|---|---|---|---|
| F01 | RDF는 관계를 subject, predicate, object triple 집합으로 표현한다 | PASS | [RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/#section-Graph-syntax) |
| F02 | OWL 2는 class, property, individual과 값에 형식 의미를 부여한다 | PASS | [OWL 2 Overview](https://www.w3.org/TR/owl2-overview/#Ontology_Documents) |
| F03 | OWL 선언만으로 발행 데이터의 필수값과 cardinality를 검사할 수 있다 | 반증 | 데이터 조건 검증은 [SHACL](https://www.w3.org/TR/shacl/)의 책임이며, `sh:minCount`, `sh:maxCount`, `sh:datatype`, `sh:closed`를 사용해야 함 |
| F04 | 계보 관계는 프로젝트 전용 용어를 새로 만들어야 한다 | 반증 | [PROV-O](https://www.w3.org/TR/prov-o/#wasDerivedFrom)는 Entity 사이 파생을 `prov:wasDerivedFrom`으로 제공함 |
| F05 | 현재 관계 질문에는 영속 graph DB가 필요하다 | 반증 | player 4,992개, team 1,938개와 observation 93개가 stdlib memory projection에서 처리됐고 동시 writer, update, query SLA 요구가 없음 |
| F06 | RDFLib는 RDF parse, serialize, in-memory graph와 SPARQL 1.1을 제공한다 | PASS | [RDFLib 공식 문서](https://rdflib.readthedocs.io/en/stable/) |
| F07 | pySHACL은 SHACL 부적합을 자동화 가능한 결과로 반환한다 | PASS | [pySHACL 공식 문서](https://github.com/RDFLib/pySHACL)는 CLI code 0, 1, 2, 3과 Python `conforms` 결과를 정의함 |
| F08 | RDFLib 7.6.0과 pySHACL 0.40.1은 현재 실행 환경에서 호환된다 | PASS | 공식 [RDFLib PyPI](https://pypi.org/project/rdflib/)와 [pySHACL PyPI](https://pypi.org/project/pyshacl/) metadata, Python 3.12.3 격리 smoke에서 valid `True`, invalid `False`, SPARQL count 1 |
| F09 | SHACL만으로 원 identity 노출을 모두 차단할 수 있다 | 반증 | SHACL은 선언된 graph 조건을 검사한다. Bronze token exact-match 검사는 기존 Python confidentiality gate로 유지해야 함 |
| F10 | 온톨로지가 REVIEW 정확도와 모집단 일반화를 개선한다 | NOT_EVALUATED | 프로젝트가 주장하지 않는 효과다. 독립 참조가 0 / 40이므로 측정 근거가 없음 |
| F11 | 현재 선택안을 동결 run에서 검증했다 | PASS | protocol 2를 51,892 triples로 투영하고 SHACL, CQ, graph, SQL, 제한 identity와 replay 검사를 통과함 |
| F12 | 2026-09-04 namespace IRI가 HTTP로 접근됐다 | 반증 | 당시 HTTPS URL은 HTTP 404였다. web 발행은 보류 중이며 `DEFERRED_PRIVATE_REPO` 기록의 비공개 전제는 잘못됐다(§17) |

## 6. Competency question으로 범위 고정

| ID | 질문 | 정답 grain | 필요한 개념과 관계 | 통과 기준 |
|---|---|---|---|---|
| CQ1 | observation이 player, match, experiment protocol과 rule protocol에 각각 연결되는가 | 전체 observation 집계 | `Observation`, `aboutPlayer`, `measuredIn`, `governedByExperiment`, `evaluatedByRule` | 다섯 count가 모두 93 |
| CQ2 | 어떤 player pair가 2개 이상 match에서 같은 team instance에 속했는가 | player pair 집계 | `ScopedPlayerIdentity`, `memberOf`, `TeamInstance`, `inMatch` | 기존 반복 pair 460개와 일치 |
| CQ3 | Manifest artifact lineage의 edge와 cycle 수는 기존 감사와 일치하는가 | lineage 집계 | `DataArtifact`, `prov:wasDerivedFrom` | edge 721개, cycle node 0개 |
| CQ4 | observation 상태 분할이 Gold 분모와 일치하는가 | 상태별 집계 | `Observation`, `analysisStatus` | evaluated 80, 세 skip 9, 2, 2 |
| CQ5 | player별 첫 evaluated 관측의 player와 REVIEW 후보 수가 SQL과 일치하는가 | primary 집계 | `Observation`, `aboutPlayer`, `recentIndex`, `reviewCandidate` | player 24명, 후보 0건 |
| CQ6 | Gold 결과가 모든 observation을 집계하는가 | result 집계 | `EvaluationResult`, `aggregatesObservation` | result 1건, observation 93건 |

- 각 class와 property는 CQ 1개 이상 또는 SHACL 품질 검사 1개 이상에 연결한다.
- 연결되지 않는 개념은 ontology 1.0 범위에서 제외한다.
- CQ 정답은 SPARQL SELECT 또는 ASK 결과와 기존 Python 또는 SQL 결과를 교차검증한다.

## 7. 선택한 표준과 도구

| 책임 | 선택 | 사용 범위 | 선택 근거 |
|---|---|---|---|
| 관계 데이터 모델 | RDF 1.1 | instance를 triple로 표현 | 표준 graph data model |
| vocabulary | RDFS, 최소 OWL 2 | class와 property 선언, label, comment, version IRI | [OWL 2](https://www.w3.org/TR/owl2-overview/)의 형식 의미와 version 규약 |
| 제약 검증 | SHACL Core | cardinality, datatype, node kind, pattern, allowed values, closed shape | [SHACL Core](https://www.w3.org/TR/shacl/#core-components)만으로 현재 조건 표현 가능 |
| 계보 | PROV-O | `prov:Entity`, `prov:Activity`, `prov:used`, `prov:wasGeneratedBy`, `prov:wasDerivedFrom` | 기존 `derived_from` 의미와 대응 |
| 질의 | SPARQL 1.1 | 6개 competency query, update와 federation 제외 | [SPARQL 1.1](https://www.w3.org/TR/sparql11-query/)은 graph pattern, property path, aggregate를 제공함 |
| authoring format | Turtle | ontology와 shape review | [Turtle](https://www.w3.org/TR/turtle/)은 compact text RDF syntax임 |
| generated format | blank-node-free N-Triples | run별 semantic sidecar | [N-Triples](https://www.w3.org/TR/n-triples/)은 line based RDF format이며 canonical layout을 정의함 |
| Python graph | RDFLib 7.6.0 exact pin | local parse, build, query, serialize | 저장소 Python 계약과 실 run에서 호환 |
| validator | pySHACL 0.40.1 exact pin | Meta-SHACL과 SHACL Core | 검증 실패와 input 또는 runtime 오류를 exit 1과 2로 분리 |
| artifact integrity | 기존 `atomic_write_bytes`, SHA-256, manifest | write, checksum, lineage, DQ | 신규 storage abstraction 불필요 |
| test runner | 기존 `unittest` | valid fixture, invalid fixture, parity, determinism | 신규 test framework 불필요 |

### 7.1 사용하지 않는 기능

- OWL reasoner를 실행하지 않는다.
- SHACL-SPARQL, SHACL Advanced, SHACL-JS를 사용하지 않는다.
- SPARQL UPDATE, SERVICE, 원격 endpoint를 사용하지 않는다.
- JSON-LD와 원격 `@context`를 사용하지 않는다.
- `owl:imports`로 원격 vocabulary를 읽지 않는다.
- graph DB, REST server, UI와 scheduler를 추가하지 않는다.

## 8. 후보 비교와 결정

| 후보 | 충족하는 요구 | 추가 운영면 | 현재 fit | 결정과 재검토 조건 |
|---|---|---|---|---|
| 기존 stdlib graph와 JSON | deterministic projection, checksum, 무의존성 | 표준 RDF parser와 SHACL validator 부재 | 기준선 | 기존 감사 도구로 유지, ontology 구현체로 확장하지 않음 |
| RDFLib와 pySHACL | RDF, SPARQL, SHACL, Python, file 실행 | direct dependency 2개와 transitive package | 적합 | 선택, exact pin과 shadow 검증 완료 |
| LinkML | YAML source에서 JSON Schema, RDF, OWL, SHACL, 언어별 model 생성 | meta-model, generator, validator surface | 과대 | [두 번째 schema target 또는 두 번째 구현 언어](https://linkml.io/linkml/generators/)가 필요할 때 재검토 |
| pyoxigraph | memory와 disk store, SPARQL 1.1, RDF format | native wheel, store lifecycle, migration | 보류 | [RDFLib memory graph](https://pyoxigraph.readthedocs.io/en/stable/)이 합의된 memory 또는 query SLA를 실패할 때 benchmark |
| Apache Jena | RDF, SPARQL, SHACL, inference, TDB2, Fuseki | JVM, store, server와 별도 운영 계약 | 부적합 | Java platform 또는 shared SPARQL service가 확정될 때 재검토 |
| Neo4j | property graph와 Cypher | 별도 DB, plugin, schema와 RDF mapping | 기각 | 사용자 결정으로 종료, 재검토 조건 없음 |

- [LinkML 공식 문서](https://linkml.io/linkml/generators/)의 강점은 다중 target generation이다. 현재 target은 RDF와 SHACL 1개 조합이므로 generation layer가 중복된다.
- [pyoxigraph 공식 문서](https://pyoxigraph.readthedocs.io/en/stable/)는 Python graph database와 SPARQL을 제공한다. 현재는 persistence와 concurrent access 요구가 없다.
- [Apache Jena 공식 문서](https://jena.apache.org/documentation/index.html)는 SHACL, TDB2, Fuseki와 inference까지 포함한다. 현재 Python batch의 최소 실행면을 초과한다.

## 9. 최소 domain model

### 9.1 Class 9개

| Class | 의미 | 식별 source | 포함 이유 |
|---|---|---|---|
| `ScopedPlayerIdentity` | season과 protocol 범위의 비식별 player key | Silver `player_key` | key scope와 동치 오판 차단 |
| `Match` | PUBG match 1건 | Silver `match_id` | observation과 team 공통 문맥 |
| `TeamInstance` | 특정 match 안의 team 1개 | 기존 graph `team_key` | 반복 teammate query |
| `Observation` | player-match R2 관측 1건 | Silver `observation_id` | 평가 grain |
| `ExperimentProtocol` | 표본, 제외, 귀속과 평가 계약 1개 | v3 `protocol_version` | 실험 계약과 룰 계약 혼동 차단 |
| `RuleProtocol` | parser와 event 해석 및 탐지 룰 계약 1개 | `rule_protocol_version` | event 계약 혼합 차단 |
| `EvaluationResult` | run의 Gold 집계 결과 1건 | run과 result dataset | Gold에서 observation 추적 |
| `DataArtifact` | manifest 관리 file 또는 외부 lineage source 1개 | path와 optional content hash 기반 IRI | PROV 계보와 checksum |
| `PipelineRun` | artifact를 사용하고 생성한 batch 1회 | `run_id` | activity와 version 문맥 |

- `DataArtifact`는 `prov:Entity`의 subclass로 선언한다.
- `PipelineRun`은 `prov:Activity`의 subclass로 선언한다.
- `Match`, `TeamInstance`, `Observation`은 PUBG telemetry 의미에 한정한다.
- Bronze event, weapon, map taxonomy, account identity class는 ontology 1.0에서 제외한다.

### 9.2 Object property 9개

| Property | Domain | Range | 방향 계약 |
|---|---|---|---|
| `memberOf` | `ScopedPlayerIdentity` | `TeamInstance` | player에서 match별 team으로 단방향 |
| `inMatch` | `TeamInstance` | `Match` | team에서 match로 단방향 |
| `aboutPlayer` | `Observation` | `ScopedPlayerIdentity` | observation에서 scoped player로 단방향 |
| `measuredIn` | `Observation` | `Match` | observation에서 match로 단방향 |
| `governedByExperiment` | player, observation, result, run | `ExperimentProtocol` | 표본과 평가 계약 연결 |
| `evaluatedByRule` | observation, result, run | `RuleProtocol` | event와 룰 계약 연결 |
| `aggregatesObservation` | `EvaluationResult` | `Observation` | Gold result에서 input observation으로 단방향 |
| `analysisStatus` | `Observation` | controlled status IRI | 배타 상태 연결 |
| `skipReason` | `Observation` | controlled status IRI | skip 원인 연결 |

- inverse property를 만들지 않는다. SPARQL inverse path로 조회한다.
- `owl:sameAs`를 생성하지 않는다. identity equality는 독립 mapping evidence가 생긴 뒤 별도 결정한다.
- teammate pair를 영속 edge로 만들지 않는다. `memberOf`와 `inMatch`에서 query 시 계산한다.
- project object property는 9개다. 계보에는 외부 vocabulary인 `prov:used`, `prov:wasGeneratedBy`,
  `prov:wasDerivedFrom`을 추가로 재사용한다.

### 9.3 핵심 datatype property

| Property | Datatype 또는 값 집합 | 제약 |
|---|---|---|
| `playerKey` | `xsd:string` | lowercase hex 24자, 정확히 1개 |
| `keyNamespace` | `xsd:anyURI` | 정확히 1개 |
| `seasonId` | `xsd:string` | 정확히 1개 |
| `matchId` | `xsd:string` | 정확히 1개 |
| `observationId` | `xsd:string` | 정확히 1개 |
| `protocolVersion`, `ruleProtocolVersion` | `xsd:string` | 각 protocol node에서 정확히 1개 |
| `analysisStatus` | project controlled IRI | `evaluated`, 세 가지 분석 skip 상태 중 정확히 1개 |
| `reviewCandidate` | `xsd:boolean` | 정확히 1개, 판정 어휘는 REVIEW 계약 유지 |
| `artifactPath` | `xsd:string` | repository relative path, 정확히 1개 |
| `sha256` | `xsd:string` | lowercase hex 64자, 정확히 1개 |
| `byteSize`, `recordCount` | `xsd:nonNegativeInteger` | 각각 정확히 1개 |

## 10. IRI, identity와 version 계약

### 10.1 Namespace 계약

- ontology IRI: `https://procloudkim.github.io/pubg-telemetry-watch/ontology/pubg-watch.ttl`.
- vocabulary namespace: ontology IRI 뒤에 `#`를 붙인다.
- version IRI: `https://procloudkim.github.io/pubg-telemetry-watch/ontology/releases/1.0.0/pubg-watch.ttl`.
- instance base: `https://procloudkim.github.io/pubg-telemetry-watch/id/`.
- stable source와 release source는 byte 단위로 같아야 한다.
- repository owner가 namespace 유지 책임을 가진다.
- `docs/ontology`는 GitHub Pages의 `docs` source 배치를 따른다. 저장소 push와 Pages 활성화 전에는
  HTTP 접근성과 content type을 보증하지 않는다.
- W3C는 IRI의 intended referent를 바꾸지 않고, namespace 소유권과 persistence 정책을 문서화하도록 권고한다. 근거는 [RDF 1.1 IRI 지침](https://www.w3.org/TR/rdf11-concepts/#section-IRIs)과 [W3C vocabulary 관리 원칙](https://www.w3.org/2006/07/SWD/Vocab/principles-20080316#uri)이다.

### 10.2 Instance IRI

- player: `id/player/{player_key}`.
- match: `id/match/{percent_encoded_match_id}`.
- team: `id/team/{team_key}`.
- observation: `id/observation/{observation_id}`.
- experiment protocol: `id/experiment-protocol/{percent_encoded_protocol_version}`.
- rule protocol: `id/rule-protocol/{percent_encoded_rule_protocol_version}`.
- result: `id/result/{percent_encoded_run_id}`.
- artifact: `id/artifact/{sha256_of_path_and_optional_content_hash}`.
- run: `id/run/{percent_encoded_run_id}`.
- source key를 표시하는 literal은 기존 Silver와 Manifest 공개 경계를 넘지 않는다.
- data graph에는 blank node를 사용하지 않는다. [RDF 1.1](https://www.w3.org/TR/rdf11-concepts/#section-blank-nodes)은 blank node label을 persistent identifier로 정의하지 않는다.

### 10.3 Version

- ontology IRI는 series를 식별하고 `owl:versionIRI`는 release를 식별한다.
- major: 기존 term 의미, domain, range 또는 필수 shape의 비호환 변경.
- minor: 기존 의미를 보존하는 class, property 또는 shape 추가.
- patch: label, comment와 문서 교정.
- deprecated term은 삭제 대신 `owl:deprecated true`와 replacement 설명을 남긴다.
- data graph는 ontology version, experiment protocol, rule protocol과 run ID를 명시한다.
- projector version과 runtime package version 및 source Manifest checksum은 semantic Manifest에 기록한다.
- [OWL 2 version IRI 규약](https://www.w3.org/TR/owl2-syntax/#Ontology_IRI_and_Version_IRI)과 [W3C version 지침](https://www.w3.org/TR/dwbp/#DataVersioning)을 적용한다.

## 11. SHACL 발행 게이트

| Shape | ERROR 조건 | 기존 검사와 관계 |
|---|---|---|
| `ScopedPlayerIdentityShape` | key, namespace, season, protocol 누락 또는 중복, key pattern 불일치 | confidentiality와 key scope 보강 |
| `MatchShape` | match ID, mode, map 누락 또는 datatype 오류 | match 문맥 고정 |
| `TeamInstanceShape` | team key 또는 `inMatch`가 정확히 1개가 아님 | membership와 orphan 검사 표준화 |
| `ExperimentProtocolShape` | experiment protocol version 누락 또는 중복 | 표본과 평가 계약 고정 |
| `RuleProtocolShape` | rule protocol version 누락 또는 중복 | event와 룰 계약 고정 |
| `ObservationShape` | player, match, 두 protocol, 상태, 분모 필드의 cardinality와 datatype 오류 | observation path와 배타 상태 표준화 |
| `DataArtifactShape` | path, hash, byte, record 누락 또는 datatype 오류 | manifest validity 보강 |
| `EvaluationResultShape` | 두 protocol, 집계 observation과 Gold 분모 필드 오류 | Gold 결과 계약 보강 |
| `PipelineRunShape` | run ID, ontology version과 두 protocol 연결 오류 | 실행 문맥 고정 |

- SHACL Core만 사용한다. cardinality는 `sh:minCount`와 `sh:maxCount`, datatype은 `sh:datatype`, 상태 집합은 `sh:in`, 미허용 property는 `sh:closed`로 검사한다.
- shape 자체는 Meta-SHACL로 먼저 검증한다.
- `conforms=false`, validator runtime error, 지원하지 않는 기능은 모두 semantic artifact 발행 실패다.
- 모든 violation은 focus node, result path, severity, message와 source shape를 machine readable report로 남긴다.
- 원 identity exact token 교집합, lineage cycle, projection parity는 기존 Python DQ를 유지한다. SHACL로 중복 구현하지 않는다.
- ontology gate PASS는 REVIEW 정확도 또는 외부 타당성 PASS를 뜻하지 않는다.

## 12. 재현성과 보안 계약

### 12.1 재현성

- ontology와 shape는 tracked Turtle file로 유지한다.
- generated data graph는 blank-node-free N-Triples로 직렬화한다.
- N-Triples 각 line을 byte 기준 정렬하고 LF와 UTF-8을 고정한다.
- W3C Canonical N-Triples는 layout을 정의하지만 triple 순서는 정의하지 않는다. line sort는 프로젝트 추가 규칙이다.
- gzip을 사용하면 `mtime=0`을 고정하고 기존 atomic replace를 재사용한다.
- 같은 input checksum, ontology version, projector version과 protocol은 같은 uncompressed SHA-256을 생성해야 한다.
- 두 번의 projection hash가 다르면 발행을 중단한다.
- semantic Manifest는 Python, RDFLib와 pySHACL version을 provenance로 포함한다. 기록된 runtime과
  다른 환경에서는 graph가 같아도 Manifest byte가 달라 write-once가 중단한다.
- 2026-09-05 Python 3.12.3 재실행은 전체 bundle PASS, Python 3.11.15 재실행은 runtime 차이로
  semantic Manifest에서 exit 2였다. 두 실행 뒤 기존 source Manifest, graph, validation과 semantic
  Manifest의 SHA-256은 유지됐다.

### 12.2 보안

- parser input은 repository 내부의 고정 Turtle file로 제한한다.
- 원격 URL parse, `owl:imports`, JSON-LD `@context`, SPARQL `SERVICE`를 금지한다.
- pySHACL은 `do_owl_imports=False`로 실행하고 query file의 `SERVICE`와 update keyword를 실행 전에 거부한다.
- query는 저장소에 동결한 SELECT만 실행하고 사용자 입력 query를 받지 않는다.
- [RDFLib 보안 문서](https://rdflib.readthedocs.io/en/stable/security_considerations/)가 경고하는 간접 network와 file 접근을 입력 경로, imports와 query 기능 제한으로 차단한다.
- ontology artifact와 validation report에 raw player name, account ID, API key를 쓰지 않는다.
- Bronze token exact-match 검사를 semantic output에도 적용한다.
- exact-match 검사는 원문 문자열 그대로의 노출만 확인한다. 변형된 식별자와 재식별 위험 전체를
  검증한 것으로 해석하지 않는다.

## 13. 배치 흐름과 실패 경계

```text
v3 Bronze + Silver + Gold + DQ PASS Manifest
                |
                v
      deterministic projector
                |
                v
        RDFLib memory graph
                |
        +-------+-------+
        |               |
        v               v
ontology.ttl      shapes.ttl
        |               |
        +-------+-------+
                |
                v
     Meta-SHACL + SHACL Core
                |
        +-------+-------+
        |               |
      FAIL             PASS
        |               |
기존 산출물 유지    CQ, SQL, Python parity
                        |
                        v
            sorted N-Triples sidecar
                        |
                        v
       validation + 별도 semantic Manifest
```

- 1단계: source manifest DQ PASS와 input checksum 재검산.
- 2단계: existing `graph_spike` key 생성 규칙을 재사용한 deterministic projection.
- 3단계: ontology와 shape parse, Meta-SHACL.
- 4단계: data graph SHACL Core validation.
- 5단계: CQ 6개 실행, 기존 graph와 SQL 집계 parity.
- 6단계: raw identity exact token 0건, projection replay hash 일치.
- 7단계: 모든 검사가 PASS일 때만 Gold 파생 semantic sidecar 2개와 별도 semantic Manifest를 write-once 발행.
- 실패 시 기존 Bronze, Silver, Gold와 v3 Manifest를 수정하지 않고 검증 실패 진단만 `reports/`에 남긴다.

## 14. 구현 시 최소 file map

| Path | 책임 | 비고 |
|---|---|---|
| `docs/ontology/pubg-watch.ttl` | stable class, property, label, version | tracked |
| `docs/ontology/releases/1.0.0/pubg-watch.ttl` | byte-identical release vocabulary | tracked |
| `docs/ontology/pubg-watch.shacl.ttl` | SHACL Core shape 9개 | tracked |
| `docs/ontology/queries/cq*.rq` | CQ 6개 | tracked |
| `src/semantic.py` | projection, validation, query, atomic publish | 신규 module 1개 |
| `tests/test_semantic.py` | valid, invalid, parity, determinism | 기존 unittest 사용 |
| `data/gold/v3/{run_id}/semantic.nt.gz` | generated graph | commit 금지 |
| `data/gold/v3/{run_id}/semantic-validation.json` | SHACL, CQ, parity와 제한 identity 검사 결과 | commit 금지 |
| `data/manifests/semantic/v3/{run_id}.json` | source와 output checksum, version, DQ | commit 금지 |

- 신규 interface, repository class, plugin system, config framework를 만들지 않는다.
- 기존 `digest`, `validate_token`, `sha256_file`, `atomic_write_bytes`를 재사용한다.
- CLI는 `python -m src.semantic --run-id <run_id>` 1개로 제한한다.
- RDFLib 7.6.0과 pySHACL 0.40.1을 `pyproject.toml`에 exact pin한다.

## 15. 단계별 적용과 중단 조건

### Phase 0 | 완료

- Neo4j 기각.
- 표준과 후보 framework 조사.
- RDFLib 7.6.0, pySHACL 0.40.1 격리 smoke.
- 최소 domain model, SHACL gate, 보안과 재현성 계약 문서화.

### Phase 1 | 승인 및 구현 완료

- 사용자 `Implement the plan`으로 direct dependency 2개와 HTTPS namespace 및 문서 구조 승인.
- RDFLib 7.6.0, pySHACL 0.40.1 exact pin.
- 완료된 `v3-20260901-r2`를 대상으로 post-run shadow 구현.
- 기존 Gold, REVIEW, 룰과 임계값 변경 0건.

### Phase 2 | shadow 검증 완료

- valid fixture, legacy protocol mapping, checksum mutation, SHACL 계약 불일치와 삽입 순서 재현성 테스트 PASS.
- observation path 93 / 93, repeated pair 460, lineage edge 721, cycle 0 parity.
- SQL evaluated 80건, primary player 24명과 REVIEW 후보 0건 parity.
- 동일 input 재실행의 uncompressed N-Triples와 gzip SHA-256 일치.
- API 호출 0회, 실 run 24.20초에서 25.88초, peak RSS 최대 233,204 KB.
- 전체 unittest 31개와 AGENTS TESTMATCH 회귀 게이트 PASS.

### Phase 3 | shadow 유지

- 인위적 checksum과 SHACL 계약 결함은 차단했지만 실 run의 고유 결함은 0건이다.
- 외부 consumer와 운영 query SLA가 없으므로 optional portfolio shadow sidecar로 유지한다.
- 고유 실결함 1건 이상 또는 외부 consumer가 생긴 경우에만 신규 protocol의 Gold 전단 gate 승격을 별도 제안한다.
- RDFLib memory 또는 query 성능이 합의된 SLA를 실패하기 전에는 store benchmark와 migration을 시작하지 않는다.
- 독립 참조가 확보되기 전에는 ontology 결과를 REVIEW 정확도 근거로 사용하지 않는다.

## 16. 구현 완료 기준

- CQ 6개에 예상 결과와 machine executable query가 존재한다.
- class와 property 100%가 CQ 또는 SHACL 검사에 연결된다.
- ontology와 shape가 parse되고 Meta-SHACL이 PASS한다.
- valid fixture와 legacy mapping이 PASS하고 checksum mutation과 SHACL 계약 불일치가 fail-closed로 끝난다.
- current run의 기존 graph와 SQL 결과가 일치한다.
- output에 raw identity exact token 0건이다.
- 같은 input의 graph hash가 두 번 일치하고 triple 삽입 순서가 달라도 정렬 결과가 같다.
- SHACL 부적합과 runtime error가 nonzero process exit로 분리된다.
- ontology, projector, protocol, source checksum이 manifest에 기록된다.
- AGENTS 회귀 게이트와 전체 tests가 PASS한다.
- README에는 ontology가 의미와 계보 gate이며 REVIEW 정확도 검증이 아님을 명시한다.

## 17. 남은 사실과 승인 항목

| 항목 | 상태 | 다음 행동 |
|---|---|---|
| RDFLib와 pySHACL local compatibility | PASS | exact pin 유지, version 변경은 별도 회귀 검증 |
| namespace ownership | PASS | GitHub repository owner와 일치 |
| namespace dereference | web 발행 보류, 당시 기록 `DEFERRED_PRIVATE_REPO` | 2026-09-10 [GitHub 저장소](https://github.com/procloudkim/pubg-telemetry-watch)와 API에서 public 확인. 비공개 전제를 교정하며 재개 결정 뒤 URL과 content type 확인 |
| current run performance | PASS | 51,892 triples, 24.20초에서 25.88초, peak RSS 최대 233,204 KB |
| semantic gate 고유 실결함 탐지 | `NOT_OBSERVED` | 인위적 checksum과 SHACL 계약 결함만 차단, shadow 유지 |
| REVIEW 정확도 영향 | `NOT_EVALUATED` | 독립 참조 재개 조건과 분리 유지 |
| identity 노출 검사 | `LIMITED_PASS` | exact token과 secret marker 및 blank node만 검사, 재식별 위험은 미평가 |
| dependency 추가 | 승인 및 반영 | RDFLib 7.6.0과 pySHACL 0.40.1 exact pin |

## 18. 1차 출처 원장

| 영역 | 출처 | 확인 내용 |
|---|---|---|
| 개발 방법 | [Ontology Development 101, Stanford](https://protege.stanford.edu/publications/ontology_development/ontology101-noy-mcguinness.html) | scope, competency question, vocabulary reuse, iterative design |
| RDF model | [RDF 1.1 Concepts, W3C](https://www.w3.org/TR/rdf11-concepts/) | triple, IRI, blank node, dataset |
| ontology language | [OWL 2 Overview, W3C](https://www.w3.org/TR/owl2-overview/) | class, property, individual, formal meaning |
| ontology version | [OWL 2 Structural Specification, W3C](https://www.w3.org/TR/owl2-syntax/#Ontology_IRI_and_Version_IRI) | ontology IRI와 version IRI |
| validation | [SHACL, W3C](https://www.w3.org/TR/shacl/) | Core constraint와 validation report |
| provenance | [PROV-O, W3C](https://www.w3.org/TR/prov-o/) | Entity, Activity, used, generated, derived |
| query | [SPARQL 1.1 Query, W3C](https://www.w3.org/TR/sparql11-query/) | graph pattern, property path, aggregate |
| authoring | [Turtle, W3C](https://www.w3.org/TR/turtle/) | compact text RDF syntax |
| generated format | [N-Triples, W3C](https://www.w3.org/TR/n-triples/) | line format, canonical layout, UTF-8 |
| publication | [Data on the Web Best Practices, W3C](https://www.w3.org/TR/dwbp/) | persistent identifier, version, provenance, formalization level |
| namespace governance | [Managing RDF Vocabularies, W3C](https://www.w3.org/2006/07/SWD/Vocab/principles-20080316) | namespace ownership, persistence, readable documentation |
| Python RDF | [RDFLib official documentation](https://rdflib.readthedocs.io/en/stable/) | parser, serializer, graph, SPARQL, supported Python |
| Python validation | [pySHACL official repository](https://github.com/RDFLib/pySHACL) | SHACL validation, API, CLI exit code, Meta-SHACL |
| RDFLib release | [RDFLib PyPI](https://pypi.org/project/rdflib/) | 7.6.0, release 2026-02-13, Python 3.8.1 이상 |
| pySHACL release | [pySHACL PyPI](https://pypi.org/project/pyshacl/) | 0.40.1, release 2026-07-28, Python 3.9 이상 |
| meta-framework | [LinkML generators](https://linkml.io/linkml/generators/) | JSON Schema, RDF, OWL, SHACL와 언어별 model generation |
| RDF store | [pyoxigraph documentation](https://pyoxigraph.readthedocs.io/en/stable/) | memory와 disk store, SPARQL, RDF format |
| JVM platform | [Apache Jena documentation](https://jena.apache.org/documentation/index.html) | RDF, SPARQL, SHACL, TDB2, Fuseki, inference |

## 19. 최종 판정

- 선택: `RDF 1.1 + 최소 RDFS/OWL 2 + SHACL Core + PROV-O + SPARQL 1.1`.
- 구현: `RDFLib 7.6.0 + pySHACL 0.40.1` exact pin.
- 저장: tracked Turtle 3개, query 6개, generated sorted N-Triples gzip과 validation JSON 1개씩 per run.
- 배치 위치: 완료된 Gold 이후 shadow, 기존 Gold와 v3 Manifest 변경 0건.
- 기각: Neo4j, LinkML, Apache Jena, persistent RDF store, reasoner, remote context.
- 동결 검증 기록: `SHADOW_VALIDATED`, `NOT_PRODUCTION_GATE`, `DEFERRED_PRIVATE_REPO`, `NO_ACCURACY_CLAIM`, `LIMITED_IDENTITY_CHECK`. 비공개 전제의 교정과 현재 발행 상태는 §17을 따른다.
- 다음 의사결정: 외부 consumer 또는 고유 실결함이 확인된 경우에만 Gold 전단 승격 검토.
