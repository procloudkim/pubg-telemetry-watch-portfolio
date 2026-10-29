# ADR 016: v3 semantic shadow sidecar
- Why 문제: JSON Manifest 무결성만으로 observation, protocol, team, Gold 결과와 lineage의 의미 계약을 기계 검증할 수 없다.
- What 결정: RDFLib 7.6.0, pySHACL 0.40.1, HTTPS namespace IRI와 ontology 1.0.0 source를 승인하고 완료된 v3 뒤의 optional shadow로 채택한다.
- How 구현: class 9개와 SHACL closed shape 9개로 RDF를 투영하고 PROV-O, CQ 6개, 기존 graph 및 SQL parity를 fail-closed로 검증한다.
- How 발행: 정렬 N-Triples gzip, validation JSON과 별도 semantic Manifest를 write-once로 쓰며 기존 v3 Gold와 Manifest는 수정하지 않는다.
- How 검증: 실 run 51,892 triples, CQ 6/6, raw token과 secret marker 및 blank node 0건, 재실행 hash 일치를 확인했다. identity 검사는 exact-match 범위다.
- 기각 대안: Neo4j, RDF store, reasoner, LinkML, Jena와 기존 Manifest 수정은 현재 query와 운영 요구를 초과한다.
- Trade-off: 의미와 계보 계약은 확보하지만 외부 consumer, REVIEW 정확도와 모집단 일반화는 입증하지 않는다.
- 상태: `SHADOW_VALIDATED`, `NOT_PRODUCTION_GATE`, `DEFERRED_PRIVATE_REPO`; 기록 runtime 재실행 PASS, API 호출 0회.
