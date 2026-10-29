# ADR 015: 파일 기반 최소 온톨로지 framework
- Why 문제: Silver와 Gold의 관계 의미, protocol 경계와 artifact 계보를 표준 계약으로 검증할 필요가 있다.
- What 결정: Neo4j를 기각하고 RDF, 최소 RDFS와 OWL 2, SHACL Core, PROV-O, SPARQL의 파일 sidecar를 설계안으로 채택한다.
- How 구현: 승인 뒤 RDFLib로 blank-node-free N-Triples를 투영하고 pySHACL로 fail-closed 검증한다.
- How 검증: competency query, 기존 graph와 SQL parity, invalid fixture, replay hash와 raw identity 0건을 강제한다.
- 기각 대안: LinkML, Apache Jena, pyoxigraph, reasoner와 영속 store는 현재 요구보다 운영면이 크다.
- Trade-off: DB 탐색성과 동시 질의는 없지만 버전, 의미, 계보와 검증을 기존 파일 pipeline 안에서 확보한다.
- 상태: `DESIGN_READY`, 의존성 추가와 runtime 구현은 별도 승인 전까지 중단한다.
