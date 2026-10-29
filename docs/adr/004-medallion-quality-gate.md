# ADR 004 — Medallion 데이터 품질 게이트
- Why: 평면 `data/`는 원문·파생물·결과의 경계와 파일 완전성을 증명하지 못했다.
- What: Bronze/Silver/Gold와 checksum·lineage·DQ manifest를 데이터 계약으로 채택한다.
- How: Bronze write-once, 파생물 atomic replace, SHA-256, 건수·참조·상태 검사를 적용한다.
- Gate: ERROR가 하나라도 있으면 Gold 결과와 검토 리포트를 발행하지 않는다.
- Legacy: 기존 해제 JSON은 원문 그대로 보존하되 `legacy_decoded_json`으로 표시한다.
- Privacy: v3 원 ID·이름은 Bronze에만 두고 Silver/Gold에는 `player_key`만 둔다.
- Trade-off: 디스크 metadata와 hash 비용이 늘지만 재수집 없이 무결성과 lineage를 재검산한다.
- Rejected: 기존 파일 삭제·재다운로드와 로컬 파일시스템에 분산 트랜잭션을 추가하는 방식.
- Source: Databricks Medallion, W3C DQV/PROV-O, NIST FIPS 180-4.
