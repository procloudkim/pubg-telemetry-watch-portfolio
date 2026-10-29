"""Materialize existing v1/v2 artifacts and validate publication lineage."""

from .ports import Clock, Files
import json
from pathlib import Path
from datetime import datetime
from src.domain.quality import _check, _quality
from src.domain.pubg.detection import mask_signals
from src.domain.pubg.parsing import (
    LEGACY_RULE_PROTOCOL_VERSION,
    RULE_PROTOCOL_VERSION,
    RULE_PROTOCOLS,
)


class Medallion:
    def __init__(self, files: Files, paths, clock: Clock):
        self.files, self.paths, self.clock = files, paths, clock

    def _artifact(self, path, layer, dataset, records, derived_from=(), source_encoding=None):
        media_type = (
            "application/gzip"
            if path.suffix == ".gz"
            else "application/x-ndjson"
            if path.suffix == ".jsonl"
            else "application/json"
        )
        item = {
            "layer": layer,
            "dataset": dataset,
            "path": path.relative_to(self.paths.root).as_posix(),
            "media_type": media_type,
            "bytes": self.files.stat(path).st_size,
            "records": records,
            "sha256": self.files.hash(path),
            "derived_from": [
                Path(value).relative_to(self.paths.root).as_posix() for value in derived_from
            ],
        }
        if source_encoding:
            item["source_encoding"] = source_encoding
        return item

    def _telemetry_target(self, version, match_id, legacy):
        existing = [
            self.paths.bronze / version / "telemetry" / f"{match_id}.json.gz",
            self.paths.bronze / version / "telemetry" / f"{match_id}.json",
        ]
        for path in existing:
            if self.files.exists(path):
                return path
        target = existing[1]
        self.files.link_or_copy(legacy, target)
        return target

    def _write_manifest(self, version, run_id, artifacts, checks, protocol_version):
        manifest = {
            "schema_version": 1,
            "dataset_version": version,
            "run_id": run_id,
            "protocol_version": protocol_version,
            "generated_at": datetime.fromisoformat(self.clock.now()).isoformat(timespec="seconds"),
            "artifacts": sorted(artifacts, key=lambda item: item["path"]),
            "quality": _quality(checks),
        }
        self.files.write_json(self.paths.manifests / f"{version}.json", manifest, indent=2)
        return manifest

    def materialize_v1(self):
        selection = json.loads(
            self.files.read_text(self.paths.data / "manifest.json", encoding="utf-8")
        )
        signals = json.loads(
            self.files.read_text(self.paths.data / "signals.json", encoding="utf-8")
        )
        gold_signals = mask_signals(signals)
        ids = [row.get("match_id") for row in selection]
        api_files = sorted(self.files.rglob(self.paths.bronze / "v1" / "api", "*.json"))
        checks = [
            _check(
                "v1.match_count", "completeness", len(ids) >= 3, len(ids), ">=3", "v1 실매치 수"
            ),
            _check(
                "v1.match_unique",
                "uniqueness",
                len(ids) == len(set(ids)),
                len(ids) - len(set(ids)),
                0,
                "selection match_id 중복 수",
            ),
            _check(
                "v1.raw_api",
                "completeness",
                len(api_files) >= len(ids) + 1,
                len(api_files),
                f">={len(ids) + 1}",
                "legacy v1 API 원문은 당시 미보존",
                severity="WARN",
            ),
        ]
        parsed_by_id = {}
        event_counts = {}
        for match_id in ids:
            telemetry = self.paths.data / f"{match_id}.telemetry.json"
            parsed = self.paths.data / f"{match_id}.parsed.json"
            checks.append(
                _check(
                    f"v1.{match_id}.files",
                    "completeness",
                    self.files.exists(telemetry) and self.files.exists(parsed),
                    int(self.files.exists(telemetry)) + int(self.files.exists(parsed)),
                    2,
                    "legacy telemetry/parsed 존재",
                )
            )
            if not self.files.exists(telemetry) or not self.files.exists(parsed):
                continue
            parsed_value = json.loads(self.files.read_text(parsed, encoding="utf-8"))
            parsed_by_id[match_id] = parsed_value
            try:
                raw_count = len(self.files.load_events(match_id, "v1"))
            except (OSError, ValueError, json.JSONDecodeError):
                raw_count = -1
            event_counts[match_id] = raw_count
            checks.append(
                _check(
                    f"v1.{match_id}.event_count",
                    "consistency",
                    raw_count == parsed_value.get("event_count"),
                    raw_count,
                    parsed_value.get("event_count"),
                    "Bronze 이벤트와 Silver event_count",
                )
            )
        signal_ids = [row.get("match_id") for row in signals]
        checks.append(
            _check(
                "v1.signal_refs",
                "referential_integrity",
                set(signal_ids) <= set(ids),
                len(set(signal_ids) - set(ids)),
                0,
                "signal의 selection 외 match 참조 수",
            )
        )
        checks.append(
            _check(
                "v1.signal_schema",
                "validity",
                all(
                    (
                        row.get("rule") in {"R1_speed", "R2_hit_ratio", "R3_kill_burst"}
                        and isinstance(row.get("evidence"), dict)
                        for row in signals
                    )
                ),
                len(signals),
                "모든 row 유효",
                "signal rule/evidence 스키마",
            )
        )
        checks.append(
            _check(
                "v1.gold_mask",
                "confidentiality",
                all(
                    (
                        row.get("player") == "pla***" and len(row.get("player_key", "")) == 24
                        for row in gold_signals
                    )
                ),
                len(gold_signals),
                "모든 row 마스킹",
                "Gold nickname·player_key",
            )
        )
        parsed_protocols = {
            row.get("rule_protocol_version", LEGACY_RULE_PROTOCOL_VERSION)
            for row in parsed_by_id.values()
        }
        signal_protocols = {
            row.get("rule_protocol_version", LEGACY_RULE_PROTOCOL_VERSION) for row in signals
        }
        protocol_ok = (
            len(parsed_protocols) == 1
            and parsed_protocols <= set(RULE_PROTOCOLS)
            and (not signal_protocols or signal_protocols == parsed_protocols)
        )
        checks.append(
            _check(
                "v1.rule_protocol",
                "consistency",
                protocol_ok,
                {"parsed": sorted(parsed_protocols), "signals": sorted(signal_protocols)},
                "단일 지원 protocol",
                "Silver·Gold 룰 protocol 일치",
            )
        )
        quality = _quality(checks)
        artifacts = []
        if quality["status"] == "PASS":
            selection_path = self.paths.silver / "v1" / "selection.json"
            self.files.write_json(selection_path, selection, indent=1)
            signal_path = self.paths.gold / "v1" / "signals.json"
            self.files.write_json(signal_path, gold_signals, indent=1)
            artifacts.append(
                self._artifact(
                    selection_path,
                    "silver",
                    "match_selection",
                    len(selection),
                    (self.paths.data / "manifest.json",),
                )
            )
            artifacts.extend(
                (
                    self._artifact(
                        path, "bronze", "api_payload", 1, source_encoding="transport_decoded_json"
                    )
                    for path in api_files
                )
            )
            for match_id in ids:
                bronze = self._telemetry_target(
                    "v1", match_id, self.paths.data / f"{match_id}.telemetry.json"
                )
                silver = self.paths.silver / "v1" / "parsed" / f"{match_id}.json"
                self.files.link_or_copy(self.paths.data / f"{match_id}.parsed.json", silver)
                encoding = "gzip" if bronze.suffix == ".gz" else "legacy_decoded_json"
                artifacts.append(
                    self._artifact(
                        bronze,
                        "bronze",
                        "telemetry_events",
                        event_counts[match_id],
                        source_encoding=encoding,
                    )
                )
                artifacts.append(
                    self._artifact(
                        silver,
                        "silver",
                        "parsed_players",
                        len(parsed_by_id[match_id]["players"]),
                        (bronze,),
                    )
                )
            artifacts.append(
                self._artifact(
                    signal_path,
                    "gold",
                    "review_signals",
                    len(gold_signals),
                    tuple(
                        (
                            self.paths.silver / "v1" / "parsed" / f"{match_id}.json"
                            for match_id in ids
                        )
                    ),
                )
            )
        rule_protocol = next(iter(parsed_protocols), LEGACY_RULE_PROTOCOL_VERSION)
        manifest_protocol = (
            "v1-rules-1"
            if rule_protocol == LEGACY_RULE_PROTOCOL_VERSION
            else "v1-rules-event-context-2"
        )
        manifest = self._write_manifest(
            "v1", "v1-public-sample", artifacts, checks, manifest_protocol
        )
        if manifest["quality"]["status"] != "PASS":
            raise RuntimeError("v1 데이터 품질 게이트 FAIL")
        return manifest

    def materialize_v2(self):
        selection = json.loads(
            self.files.read_text(self.paths.data / "elite-manifest.json", encoding="utf-8")
        )
        baseline = json.loads(
            self.files.read_text(self.paths.data / "elite-baseline.json", encoding="utf-8")
        )
        ids = [row.get("match_id") for row in selection]
        cohort = baseline.get("cohort") or {}
        rule = baseline.get("current_match_rule") or {}
        if "evaluated_observations" not in rule:
            legacy_denominator = rule.pop("eligible_elite_observations", None)
            legacy_rate = rule.get(
                "review_candidate_rate", rule.get("false_positive_candidate_rate")
            )
            rule.pop("false_positive_candidate_rate", None)
            rule.update(
                {
                    "target_observations": None,
                    "evaluated_observations": None,
                    "skipped_observations": None,
                    "skipped_by_reason": {},
                    "review_candidate_rate": None,
                    "denominator_status": "UNAVAILABLE_LEGACY",
                    "legacy_qualified_observations": legacy_denominator,
                    "legacy_recorded_review_candidate_rate": legacy_rate,
                }
            )
            denominator_check = _check(
                "v2.rule_denominator",
                "completeness",
                False,
                {
                    "signals": rule.get("signals"),
                    "legacy_qualified_observations": legacy_denominator,
                },
                "evaluated/skipped/candidate",
                "legacy 실행은 실제 매치별 평가 분모를 기록하지 않음",
                severity="WARN",
            )
        else:
            target = rule.get("target_observations")
            evaluated = rule.get("evaluated_observations")
            skipped = rule.get("skipped_observations")
            reasons = rule.get("skipped_by_reason") or {}
            signals = rule.get("signals")
            rate = rule.get("review_candidate_rate")
            counts_valid = all(
                (
                    isinstance(value, int) and value >= 0
                    for value in (target, evaluated, skipped, signals)
                )
            )
            reasons_valid = isinstance(reasons, dict) and all(
                (isinstance(value, int) and value >= 0 for value in reasons.values())
            )
            reason_total = sum(reasons.values()) if reasons_valid else None
            expected_rate = signals / evaluated if counts_valid and evaluated else None
            valid = (
                counts_valid
                and reasons_valid
                and (target == evaluated + skipped)
                and (skipped == reason_total)
                and (signals <= evaluated)
                and (rate == expected_rate)
                and (rule.get("denominator_status") == "MEASURED")
            )
            denominator_check = _check(
                "v2.rule_denominator",
                "consistency",
                valid,
                {
                    "target": target,
                    "evaluated": evaluated,
                    "skipped": skipped,
                    "skip_reasons": reason_total,
                    "signals": signals,
                    "rate": rate,
                },
                {
                    "target": "evaluated + skipped",
                    "skipped": "sum(skipped_by_reason)",
                    "rate": "signals / evaluated",
                },
                "현 R2의 배타적 분모 등식",
            )
        api_files = sorted(self.files.rglob(self.paths.bronze / "v2" / "api", "*.json"))
        checks = [
            _check(
                "v2.match_unique",
                "uniqueness",
                len(ids) == len(set(ids)),
                len(ids) - len(set(ids)),
                0,
                "selection match_id 중복 수",
            ),
            _check(
                "v2.match_count",
                "consistency",
                cohort.get("unique_matches") == len(ids),
                len(ids),
                cohort.get("unique_matches"),
                "selection과 baseline unique match 수",
            ),
            denominator_check,
            _check(
                "v2.raw_api",
                "completeness",
                len(api_files) >= len(ids) + 3,
                len(api_files),
                f">={len(ids) + 3}",
                "legacy v2 API 원문은 당시 미보존",
                severity="WARN",
            ),
        ]
        parsed_by_id = {}
        event_counts = {}
        for match_id in ids:
            telemetry = self.paths.data / f"{match_id}.telemetry.json"
            parsed = self.paths.data / f"{match_id}.parsed.json"
            checks.append(
                _check(
                    f"v2.{match_id}.files",
                    "completeness",
                    self.files.exists(telemetry) and self.files.exists(parsed),
                    int(self.files.exists(telemetry)) + int(self.files.exists(parsed)),
                    2,
                    "legacy telemetry/parsed 존재",
                )
            )
            if not self.files.exists(telemetry) or not self.files.exists(parsed):
                continue
            parsed_value = json.loads(self.files.read_text(parsed, encoding="utf-8"))
            parsed_by_id[match_id] = parsed_value
            try:
                raw_count = len(self.files.load_events(match_id, "v2"))
            except (OSError, ValueError, json.JSONDecodeError):
                raw_count = -1
            event_counts[match_id] = raw_count
            checks.append(
                _check(
                    f"v2.{match_id}.event_count",
                    "consistency",
                    raw_count == parsed_value.get("event_count"),
                    raw_count,
                    parsed_value.get("event_count"),
                    "Bronze 이벤트와 Silver event_count",
                )
            )
        expected_rule_protocol = baseline.get("rule_protocol_version", LEGACY_RULE_PROTOCOL_VERSION)
        parsed_protocols = {
            row.get("rule_protocol_version", LEGACY_RULE_PROTOCOL_VERSION)
            for row in parsed_by_id.values()
        }
        checks.append(
            _check(
                "v2.rule_protocol",
                "consistency",
                expected_rule_protocol in RULE_PROTOCOLS
                and parsed_protocols == {expected_rule_protocol},
                {"baseline": expected_rule_protocol, "parsed": sorted(parsed_protocols)},
                "baseline과 모든 parsed 일치",
                "v2 룰 protocol",
            )
        )
        quality = _quality(checks)
        artifacts = []
        if quality["status"] == "PASS":
            selection_path = self.paths.silver / "v2" / "selection.json"
            baseline_path = self.paths.gold / "v2" / "baseline.json"
            self.files.write_json(selection_path, selection, indent=1)
            self.files.write_json(baseline_path, baseline, indent=1)
            artifacts.append(
                self._artifact(
                    selection_path,
                    "silver",
                    "match_selection",
                    len(selection),
                    (self.paths.data / "elite-manifest.json",),
                )
            )
            artifacts.extend(
                (
                    self._artifact(
                        path, "bronze", "api_payload", 1, source_encoding="transport_decoded_json"
                    )
                    for path in api_files
                )
            )
            for match_id in ids:
                bronze = self._telemetry_target(
                    "v2", match_id, self.paths.data / f"{match_id}.telemetry.json"
                )
                silver = self.paths.silver / "v2" / "parsed" / f"{match_id}.json"
                self.files.link_or_copy(self.paths.data / f"{match_id}.parsed.json", silver)
                encoding = "gzip" if bronze.suffix == ".gz" else "legacy_decoded_json"
                artifacts.append(
                    self._artifact(
                        bronze,
                        "bronze",
                        "telemetry_events",
                        event_counts[match_id],
                        source_encoding=encoding,
                    )
                )
                artifacts.append(
                    self._artifact(
                        silver,
                        "silver",
                        "parsed_players",
                        len(parsed_by_id[match_id]["players"]),
                        (bronze,),
                    )
                )
            artifacts.append(
                self._artifact(
                    baseline_path,
                    "gold",
                    "r2_baseline",
                    1,
                    tuple(
                        (
                            self.paths.silver / "v2" / "parsed" / f"{match_id}.json"
                            for match_id in ids
                        )
                    ),
                )
            )
        manifest_protocol = (
            "v2-r2-baseline-3"
            if expected_rule_protocol == RULE_PROTOCOL_VERSION
            else "v2-r2-baseline-2"
        )
        manifest = self._write_manifest(
            "v2", "v2-top10-baseline", artifacts, checks, manifest_protocol
        )
        if manifest["quality"]["status"] != "PASS":
            raise RuntimeError("v2 데이터 품질 게이트 FAIL")
        return manifest

    def verify_manifest(self, version):
        path = self.paths.manifests / f"{version}.json"
        manifest = json.loads(self.files.read_text(path, encoding="utf-8"))
        self.verify_artifacts(manifest)
        return manifest

    def verify_artifacts(self, manifest):
        if manifest.get("quality", {}).get("status") != "PASS":
            raise RuntimeError(f"{manifest.get('dataset_version')} manifest DQ FAIL")
        for artifact in manifest.get("artifacts", []):
            target = self.paths.root / artifact["path"]
            if not self.files.exists(target) or self.files.hash(target) != artifact["sha256"]:
                raise RuntimeError(f"manifest checksum 불일치: {artifact['path']}")
        return True

    def write_quality_report(self, manifests):
        lines = [
            "# Data Quality",
            "",
            "| 버전 | 상태 | artifacts | ERROR | WARN |",
            "|---|---:|---:|---:|---:|",
        ]
        for manifest in manifests:
            checks = manifest["quality"]["checks"]
            errors = sum((row["status"] == "FAIL" and row["severity"] == "ERROR" for row in checks))
            warnings = sum(
                (row["status"] == "FAIL" and row["severity"] == "WARN" for row in checks)
            )
            lines.append(
                f"| {manifest['dataset_version']} | {manifest['quality']['status']} | {len(manifest['artifacts'])} | {errors} | {warnings} |"
            )
        lines += [
            "",
            "각 파일의 SHA-256·byte·record count·lineage와 개별 검사 결과는 `data/manifests/` JSON이 정본이다.",
        ]
        self.files.mkdir(self.paths.reports, exist_ok=True)
        self.files.write_bytes(self.paths.reports / "data-quality.md", "\n".join(lines).encode())
