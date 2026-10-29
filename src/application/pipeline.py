"""Legacy batch parsing, detection and publication use cases."""

from .ports import Clock, Files
import json
from src.domain.pubg.parsing import (
    LEGACY_RULE_PROTOCOL_VERSION,
    RULE_PROTOCOL_VERSION,
    RULE_PROTOCOLS,
    parse_events,
)
from src.domain.pubg.detection import detect_match, mask_signals


class Pipeline:
    def __init__(self, files: Files, paths, clock: Clock, medallion, presentation, emit):
        self.files, self.paths, self.clock = files, paths, clock
        self.medallion, self.presentation, self.emit = medallion, presentation, emit

    def parse_match(
        self, match_id, *, version=None, run_id=None, rule_protocol=RULE_PROTOCOL_VERSION
    ):
        return parse_events(
            match_id, self.files.load_events(match_id, version, run_id), rule_protocol=rule_protocol
        )

    def parse(self, match, rule_protocol):
        selection = self.paths.silver / "v1" / "selection.json"
        ids = (
            [match]
            if match
            else [
                m["match_id"]
                for m in json.loads(
                    self.files.read_text(
                        selection
                        if self.files.exists(selection)
                        else self.paths.data / "manifest.json",
                        encoding="utf-8",
                    )
                )
            ]
        )
        for mid in ids:
            out = self.parse_match(mid, version="v1", rule_protocol=rule_protocol)
            self.files.write_json(self.paths.silver / "v1" / "parsed" / f"{mid}.json", out)
            self.files.write_json(self.paths.data / f"{mid}.parsed.json", out)
            self.emit(
                f"파싱: {mid} 이벤트 {out['event_count']:,} 플레이어 {len(out['players'])} protocol={rule_protocol}"
            )

    def detect(self, match):
        selection_path = self.paths.silver / "v1" / "selection.json"
        selection = json.loads(
            self.files.read_text(
                selection_path
                if self.files.exists(selection_path)
                else self.paths.data / "manifest.json",
                encoding="utf-8",
            )
        )
        ids = [match] if match else [m["match_id"] for m in selection]
        all_signals = []
        protocols = set()
        for mid in ids:
            silver = self.paths.silver / "v1" / "parsed" / f"{mid}.json"
            parsed = json.loads(
                self.files.read_text(
                    silver if self.files.exists(silver) else self.paths.data / f"{mid}.parsed.json",
                    encoding="utf-8",
                )
            )
            if parsed.get("match_id") != mid:
                raise SystemExit(f"parsed match_id 불일치: {mid}")
            protocol = parsed.get("rule_protocol_version", LEGACY_RULE_PROTOCOL_VERSION)
            if protocol not in RULE_PROTOCOLS:
                raise SystemExit(f"parsed rule protocol 불일치: {mid} {protocol}")
            protocols.add(protocol)
            players = parsed["players"]
            sig = detect_match(parsed)
            all_signals += sig
            self.emit(f"탐지: {mid} 신호 {len(sig)}건 (플레이어 {len(players)})")
        if (
            len(protocols) != 1
            or len(ids) != len(set(ids))
            or any(
                (
                    s["match_id"] not in ids
                    or s["rule"] not in {"R1_speed", "R2_hit_ratio", "R3_kill_burst"}
                    or (not isinstance(s.get("evidence"), dict))
                    for s in all_signals
                )
            )
        ):
            raise SystemExit("v1 Gold 품질 검사 실패")
        self.files.write_json(
            self.paths.gold / "v1" / "signals.json", mask_signals(all_signals), indent=1
        )
        self.files.write_json(self.paths.data / "signals.json", all_signals, indent=1)

    def report(self, match):
        if match:
            signals = json.loads(
                self.files.read_text(self.paths.data / "signals.json", encoding="utf-8")
            )
            if any((row.get("match_id") != match for row in signals)):
                raise SystemExit("합성 게이트 signal match_id 불일치")
            known = json.loads(
                self.files.read_text(self.paths.data / "manifest.json", encoding="utf-8")
            )
            manifest = [
                next(
                    (row for row in known if row.get("match_id") == match),
                    {"match_id": match, "mode": "synthetic", "map": "synthetic"},
                )
            ]
        else:
            self.medallion.materialize_v1()
            self.medallion.verify_manifest("v1")
            signals = json.loads(
                self.files.read_text(self.paths.gold / "v1" / "signals.json", encoding="utf-8")
            )
            manifest = json.loads(
                self.files.read_text(self.paths.data / "manifest.json", encoding="utf-8")
            )
        self.files.write_bytes(
            self.paths.reports / "review-queue.md", self.render_review(signals, manifest)
        )
        self.emit(f"리포트: reports/review-queue.md ({len(signals)}건)")

    def render_review(self, signals, manifest, generated_at=None):
        return self.presentation.render_review(
            signals, manifest, generated_at=generated_at or self.clock.now(timespec="seconds")
        )
