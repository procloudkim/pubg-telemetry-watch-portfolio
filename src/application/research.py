"""Frozen v3 protocol, collection budget and evaluation orchestration."""

from .ports import Clock, Environment, Files, PubgTransport
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import quote
from src.domain.errors import BudgetExhausted, TransportError
from src.domain.serialization import stable_json, digest
from src.domain.tokens import validate_token
from src.domain.ledger import _ledger_requests
from src.domain.quality import _quality
from src.domain.pubg.parsing import LEGACY_RULE_PROTOCOL_VERSION, RULE_PROTOCOL_VERSION
from src.domain.pubg.detection import (
    MIN_ATTACKS,
    MIN_R2_POOL,
    MIN_R2_SIGNAL_POOL,
    Z_HIT,
    r2_observation,
)
from src.domain.pubg.selection import current_season, top_players, telemetry_url
from src.domain.pubg.privacy import _pseudonymous_parsed
from src.domain.research import (
    LEGACY_PROTOCOL_VERSION,
    PROTOCOL_VERSION,
    COHORT_SIZE,
    MATCHES_PER_PLAYER,
    API_INTERVAL_S,
    MIN_PRIMARY_PLAYERS,
    MIN_SECONDARY_OBSERVATIONS,
    REVIEW_RATE_GUARDRAIL,
    make_cohort,
    candidate_matches,
    cohort_preflight,
    cluster_bootstrap_interval,
    primary_decision,
    _rate_summary,
    _subgroups,
    _status_groups,
    _v3_checks,
)


# Reservations are durable before transport; uncertain requests consume the same session budget.
class ApiSession:
    def __init__(
        self,
        global_ledger,
        run_ledger,
        session_id,
        limit,
        *,
        files: Files,
        clock: Clock,
        http: PubgTransport,
        environment: Environment,
    ):
        self.files, self.clock, self.http, self.environment = (files, clock, http, environment)
        if not 1 <= limit <= 60:
            raise SystemExit("--api-call-limit은 1~60")
        self.global_ledger, self.run_ledger = (global_ledger, run_ledger)
        self.session_id = validate_token(session_id, "--session-id")
        self.limit = limit
        self.run_key = (
            self.files.resolve(run_ledger)
            .relative_to(self.files.resolve(global_ledger.parent))
            .as_posix()
        )
        if self.files.resolve(global_ledger) == self.files.resolve(run_ledger):
            raise ValueError("전역/실행 원장은 다른 경로여야 함")
        self.records = self.files.read_ledger(global_ledger)
        self.rows = _ledger_requests(self.records)
        run_records = self.files.read_ledger(run_ledger)
        _ledger_requests(run_records)
        existing = {
            (r.get("request_id"), r.get("phase")): r for r in run_records if "schema_version" in r
        }
        authoritative = {
            (r["request_id"], r["phase"]): r
            for r in self.records
            if r.get("run_ledger") == self.run_key
        }
        if any(
            (key not in authoritative or authoritative[key] != row for key, row in existing.items())
        ):
            raise ValueError("실행 원장과 전역 원장 불일치")
        for key, row in authoritative.items():
            if key not in existing:
                self.files.append_ledger(run_ledger, row)
        self.used = sum(
            (
                row.get("session_id") == session_id and (not row.get("cache_hit", False))
                for row in self.rows
            )
        )
        self.resume_after = (
            self.clock.monotonic() + API_INTERVAL_S
            if any((row.get("phase") == "reserved" for row in self.rows))
            else None
        )

    def _append(self, row):
        self.files.append_ledger(self.global_ledger, row)
        self.records.append(row)
        self.rows = _ledger_requests(self.records)
        self.files.append_ledger(self.run_ledger, row)

    def get(self, path, cache_path):
        if self.files.exists(cache_path):
            return json.loads(self.files.read_text(cache_path, encoding="utf-8"))
        if self.used >= self.limit:
            raise BudgetExhausted(f"API 호출 예산 소진: {self.used}/{self.limit}")
        self.http.authorize()
        if self.resume_after is not None:
            while (remaining := (self.resume_after - self.clock.monotonic())) > 0:
                self.clock.sleep(remaining)
            self.resume_after = None
        network = [
            row for row in self.rows if not row.get("cache_hit", False) and row.get("requested_at")
        ]
        if network:
            last = datetime.fromisoformat(
                network[-1].get("finished_at") or network[-1]["requested_at"]
            )
            while (
                elapsed := (datetime.fromisoformat(self.clock.now()) - last).total_seconds()
            ) < API_INTERVAL_S:
                self.clock.sleep(API_INTERVAL_S - elapsed)
        reservation = {
            "schema_version": 2,
            "request_id": self.environment.request_id(),
            "phase": "reserved",
            "run_ledger": self.run_key,
            "session_id": self.session_id,
            "requested_at": datetime.fromisoformat(self.clock.now()).isoformat(
                timespec="microseconds"
            ),
            "endpoint": path,
            "cache_hit": False,
        }
        self.used += 1
        self._append(reservation)
        status = None
        try:
            response = self.http.request(path)
            status = response.status_code
            response.raise_for_status()
            value = response.json()
            self.files.write_once(cache_path, response.content)
            return value
        finally:
            self._append(
                {
                    **reservation,
                    "phase": "completed",
                    "http_status": status,
                    "finished_at": datetime.fromisoformat(self.clock.now()).isoformat(
                        timespec="microseconds"
                    ),
                }
            )


class Research:
    def __init__(
        self,
        files: Files,
        paths,
        clock: Clock,
        http: PubgTransport,
        environment: Environment,
        pipeline,
        medallion,
        emit,
    ):
        self.files, self.paths, self.clock = files, paths, clock
        self.http, self.environment, self.pipeline = http, environment, pipeline
        self.medallion, self.emit = medallion, emit

    def utc_now(self):
        return self.clock.now(timespec="seconds")

    def api_session(self, global_ledger, run_ledger, session_id, limit):
        return ApiSession(
            global_ledger,
            run_ledger,
            session_id,
            limit,
            files=self.files,
            clock=self.clock,
            http=self.http,
            environment=self.environment,
        )

    def _write_preflight(self, cohort, silver):
        report = cohort_preflight(cohort)
        self.files.write_json(silver / "preflight.json", report, indent=2)
        return report

    def _require_preflight(self, report):
        if report["status"] != "PASS":
            raise SystemExit(
                f"v3 preflight FAIL: source_players={report['source_reference_players']}/{COHORT_SIZE}, owner_players={report['candidate_owner_players']}/{COHORT_SIZE}; collect 차단"
            )

    def preflight_run(self, run_id):
        _, silver, _ = self.run_paths(run_id)
        cohort_path = silver / "cohort.json"
        if not self.files.exists(cohort_path):
            raise SystemExit("먼저 v3 init 실행 필요")
        report = self._write_preflight(
            json.loads(self.files.read_text(cohort_path, encoding="utf-8")), silver
        )
        self.emit(
            f"v3 preflight: {report['status']} source={report['source_reference_players']} owner={report['candidate_owner_players']} candidates={report['candidate_matches']}",
            flush=True,
        )
        self._require_preflight(report)
        return report

    def run_paths(self, run_id):
        validate_token(run_id, "--run-id")
        return (
            self.paths.bronze / "v3" / run_id,
            self.paths.silver / "v3" / run_id,
            self.paths.gold / "v3" / run_id,
        )

    def prior_exposure(self, protocol_version=PROTOCOL_VERSION, exclude_run_id=None):
        if protocol_version not in {LEGACY_PROTOCOL_VERSION, PROTOCOL_VERSION}:
            raise ValueError(f"지원하지 않는 v3 protocol: {protocol_version}")
        match_ids, hashes, paths = (set(), {}, [])
        selections = {
            "v1": (self.paths.silver / "v1" / "selection.json", self.paths.data / "manifest.json"),
            "v2": (
                self.paths.silver / "v2" / "selection.json",
                self.paths.data / "elite-manifest.json",
            ),
        }
        for version, candidates in selections.items():
            path = next(
                (candidate for candidate in candidates if self.files.exists(candidate)), None
            )
            if path is None:
                continue
            rows = json.loads(self.files.read_text(path, encoding="utf-8"))
            ids = [row.get("match_id") for row in rows]
            if any((not isinstance(match_id, str) or not match_id for match_id in ids)):
                raise ValueError(f"{version} selection match_id 스키마 오류")
            match_ids.update(ids)
            hashes[version] = self.files.hash(path)
            paths.append(path)
        if protocol_version == PROTOCOL_VERSION:
            for path in sorted(self.files.glob(self.paths.silver / "v3", "*/cohort.json")):
                if path.parent.name == exclude_run_id:
                    continue
                cohort = json.loads(self.files.read_text(path, encoding="utf-8"))
                if cohort.get("protocol_version") not in {
                    LEGACY_PROTOCOL_VERSION,
                    PROTOCOL_VERSION,
                }:
                    raise ValueError(f"이전 v3 cohort protocol 오류: {path.parent.name}")
                ids = [row.get("match_id") for row in candidate_matches(cohort)]
                if any((not isinstance(match_id, str) or not match_id for match_id in ids)):
                    raise ValueError(f"이전 v3 cohort match_id 스키마 오류: {path.parent.name}")
                match_ids.update(ids)
                hashes[f"v3:{path.parent.name}"] = self.files.hash(path)
                paths.append(path)
        return (match_ids, hashes, paths)

    def ensure_protocol(self, bronze):
        path = bronze / "protocol.json"
        if self.files.exists(path):
            protocol = json.loads(self.files.read_text(path, encoding="utf-8"))
            version = protocol.get("protocol_version")
            if version not in {LEGACY_PROTOCOL_VERSION, PROTOCOL_VERSION}:
                raise SystemExit(f"지원하지 않는 v3 protocol: {version}")
            prior_policy = (
                "exclude_v1_v2_first5_without_backfill"
                if version == LEGACY_PROTOCOL_VERSION
                else "exclude_v1_v2_prior_v3_candidates_first5_without_backfill"
            )
            fixed = {
                "protocol_version": version,
                "cohort_size": COHORT_SIZE,
                "matches_per_player": MATCHES_PER_PLAYER,
                "mode": "squad-fpp",
                "platform_region": "pc-as",
                "shard": "steam",
                "prior_exposure_policy": prior_policy,
                "r2": {
                    "min_attacks": MIN_ATTACKS,
                    "context_minimum_pool": MIN_R2_POOL,
                    "signal_capable_pool": MIN_R2_SIGNAL_POOL,
                    "z_threshold": Z_HIT,
                },
                "primary_guardrail": REVIEW_RATE_GUARDRAIL,
            }
            if version == PROTOCOL_VERSION:
                fixed["rule_protocol_version"] = RULE_PROTOCOL_VERSION
                fixed["r2"]["event_filter"] = "damage>0+matching_attackId"
            if any((protocol.get(key) != value for key, value in fixed.items())):
                raise SystemExit("기존 run의 고정 protocol과 현재 코드 불일치")
            return protocol
        excluded_match_ids, prior_hashes, _ = self.prior_exposure(PROTOCOL_VERSION, bronze.name)
        protocol = {
            "protocol_version": PROTOCOL_VERSION,
            "snapshot_started_at": self.utc_now(),
            "rule_protocol_version": RULE_PROTOCOL_VERSION,
            "cohort_size": COHORT_SIZE,
            "matches_per_player": MATCHES_PER_PLAYER,
            "mode": "squad-fpp",
            "platform_region": "pc-as",
            "shard": "steam",
            "prior_exposure_policy": "exclude_v1_v2_prior_v3_candidates_first5_without_backfill",
            "excluded_prior_match_ids": sorted(excluded_match_ids),
            "prior_selection_sha256": prior_hashes,
            "r2": {
                "min_attacks": MIN_ATTACKS,
                "context_minimum_pool": MIN_R2_POOL,
                "signal_capable_pool": MIN_R2_SIGNAL_POOL,
                "z_threshold": Z_HIT,
                "event_filter": "damage>0+matching_attackId",
            },
            "primary_guardrail": REVIEW_RATE_GUARDRAIL,
        }
        self.files.write_once(path, stable_json(protocol))
        return protocol

    def init_run(self, run_id, session_id, api_call_limit):
        bronze, silver, _ = self.run_paths(run_id)
        protocol = self.ensure_protocol(bronze)
        excluded_match_ids = set(protocol["excluded_prior_match_ids"])
        prior_hashes = protocol["prior_selection_sha256"]
        cohort_path = silver / "cohort.json"
        if self.files.exists(cohort_path):
            cohort = json.loads(self.files.read_text(cohort_path, encoding="utf-8"))
            preflight = self._write_preflight(cohort, silver)
            self.emit(f"v3 init: frozen cohort 재사용 {run_id} preflight={preflight['status']}")
            self._require_preflight(preflight)
            return cohort
        client = self.api_session(
            self.paths.bronze / "v3" / "session-ledger.jsonl",
            bronze / "api-ledger.jsonl",
            session_id,
            api_call_limit,
        )
        seasons_path = bronze / "api" / "seasons.json"
        seasons = client.get("/shards/steam/seasons", seasons_path)
        season_id = current_season(seasons)
        leaderboard_path = bronze / "api" / "leaderboard.json"
        leaderboard = client.get(
            f"/shards/pc-as/leaderboards/{season_id}/squad-fpp", leaderboard_path
        )
        leaders = top_players(leaderboard, COHORT_SIZE)
        if sorted((row["attributes"]["rank"] for row in leaders)) != list(
            range(1, COHORT_SIZE + 1)
        ):
            raise ValueError("leaderboard rank 1~100 완전성 실패")
        player_payloads, player_paths = ([], [])
        ids = [row["id"] for row in leaders]
        for batch_index in range(0, COHORT_SIZE, 10):
            batch = ids[batch_index : batch_index + 10]
            path = bronze / "api" / "players" / f"{batch_index // 10 + 1:02d}.json"
            payload = client.get(
                f"/shards/steam/players?filter[playerIds]={quote(','.join(batch), safe=',')}", path
            )
            player_payloads.append(payload)
            player_paths.append(path)
        source_hashes = {
            "seasons": self.files.hash(seasons_path),
            "leaderboard": self.files.hash(leaderboard_path),
            "player_batches": [self.files.hash(path) for path in player_paths],
        }
        if prior_hashes:
            source_hashes["prior_selections"] = prior_hashes
        cohort = make_cohort(
            leaders,
            player_payloads,
            season_id,
            protocol["snapshot_started_at"],
            self.utc_now(),
            source_hashes,
            excluded_match_ids,
            protocol_version=protocol["protocol_version"],
        )
        self.files.write_once(cohort_path, stable_json(cohort))
        preflight = self._write_preflight(cohort, silver)
        self.emit(
            f"v3 init: top{len(cohort['players'])} holdout=100 prior_excluded={cohort['prior_excluded_references']} preflight={preflight['status']} API={client.used}/{client.limit}"
        )
        self._require_preflight(preflight)
        return cohort

    def _match_cache(self, bronze, match_id):
        return bronze / "api" / "matches" / f"{match_id}.json"

    def _has_telemetry(self, bronze, match_id):
        return any(
            (
                self.files.exists(bronze / "telemetry" / f"{match_id}{suffix}")
                for suffix in (".json.gz", ".json")
            )
        )

    def collection_summary(self, cohort, bronze):
        counts = Counter()
        failed = set()
        ledger = bronze / "api-ledger.jsonl"
        for row in _ledger_requests(self.files.read_ledger(ledger)):
            endpoint = row.get("endpoint", "")
            if "/matches/" in endpoint and (
                row.get("http_status") is None or row["http_status"] >= 400
            ):
                failed.add(endpoint.rsplit("/", 1)[-1])
        for row in candidate_matches(cohort):
            cache = self._match_cache(bronze, row["match_id"])
            if not self.files.exists(cache):
                counts["api_error" if row["match_id"] in failed else "pending"] += 1
                continue
            match = json.loads(self.files.read_text(cache, encoding="utf-8"))
            if match["data"]["attributes"].get("gameMode") != "squad-fpp":
                counts["mode_excluded"] += 1
            elif self._has_telemetry(bronze, row["match_id"]):
                counts["ready"] += 1
            else:
                counts["telemetry_pending"] += 1
        counts["frozen_unique_references"] = sum(counts.values())
        return dict(counts)

    def collect_run(self, run_id, session_id, api_call_limit):
        bronze, silver, _ = self.run_paths(run_id)
        cohort_path = silver / "cohort.json"
        if not self.files.exists(cohort_path):
            raise SystemExit("먼저 v3 init 실행 필요")
        cohort = json.loads(self.files.read_text(cohort_path, encoding="utf-8"))
        self._require_preflight(self._write_preflight(cohort, silver))
        client = self.api_session(
            self.paths.bronze / "v3" / "session-ledger.jsonl",
            bronze / "api-ledger.jsonl",
            session_id,
            api_call_limit,
        )
        for row in candidate_matches(cohort):
            match_id = row["match_id"]
            cache = self._match_cache(bronze, match_id)
            changed = not self.files.exists(cache)
            try:
                match = client.get(f"/shards/steam/matches/{match_id}", cache)
            except BudgetExhausted as error:
                self.emit(error)
                break
            except TransportError:
                self.files.write_json(
                    silver / "collection.json", self.collection_summary(cohort, bronze), indent=2
                )
                self.emit(f"v3 collect: match 요청 실패, 다음 실행에서 재시도 ({match_id})")
                break
            if match.get("data", {}).get("id") != match_id:
                raise ValueError(f"match 응답 ID 불일치: {match_id}")
            if match["data"]["attributes"].get("gameMode") == "squad-fpp" and (
                not self._has_telemetry(bronze, match_id)
            ):
                try:
                    self.http.download_telemetry(
                        telemetry_url(match),
                        match_id,
                        version="v3",
                        run_id=run_id,
                        compatibility_copy=False,
                    )
                    changed = True
                except TransportError:
                    self.files.write_json(
                        silver / "collection.json",
                        self.collection_summary(cohort, bronze),
                        indent=2,
                    )
                    self.emit(f"v3 collect: telemetry 요청 실패, 다음 실행에서 재시도 ({match_id})")
                    break
            if changed:
                self.files.write_json(
                    silver / "collection.json", self.collection_summary(cohort, bronze), indent=2
                )
        summary = self.collection_summary(cohort, bronze)
        self.files.write_json(silver / "collection.json", summary, indent=2)
        self.emit(f"v3 collect: {summary} API={client.used}/{client.limit}")
        return summary

    def _identities(self, bronze, season_id, protocol_version):
        leaderboard = json.loads(
            self.files.read_text(bronze / "api" / "leaderboard.json", encoding="utf-8")
        )
        return {
            digest(protocol_version, season_id, row["id"])[:24]: {
                "account_id": row["id"],
                "name": row["attributes"].get("name"),
            }
            for row in top_players(leaderboard, COHORT_SIZE)
        }

    def _snapshot_consistency(self, cohort, bronze, protocol):
        seasons_path = bronze / "api" / "seasons.json"
        leaderboard_path = bronze / "api" / "leaderboard.json"
        player_paths = sorted(self.files.glob(bronze / "api" / "players", "*.json"))
        actual_hashes = {
            "seasons": self.files.hash(seasons_path),
            "leaderboard": self.files.hash(leaderboard_path),
            "player_batches": [self.files.hash(path) for path in player_paths],
        }
        _, prior_hashes, _ = self.prior_exposure(cohort["protocol_version"], bronze.name)
        frozen_prior = protocol.get("prior_selection_sha256", {})
        prior_hashes = {key: prior_hashes.get(key) for key in frozen_prior}
        if "prior_selections" in cohort.get("source_sha256", {}):
            actual_hashes["prior_selections"] = prior_hashes
        leaderboard = json.loads(self.files.read_text(leaderboard_path, encoding="utf-8"))
        payloads = [
            json.loads(self.files.read_text(path, encoding="utf-8")) for path in player_paths
        ]
        expected = make_cohort(
            top_players(leaderboard, COHORT_SIZE),
            payloads,
            cohort["season_id"],
            cohort["snapshot_started_at"],
            cohort["snapshot_completed_at"],
            actual_hashes,
            protocol.get("excluded_prior_match_ids", ()),
            protocol_version=cohort["protocol_version"],
        )
        reproducible = expected["players"] == cohort.get("players") and expected[
            "excluded_prior_match_ids"
        ] == cohort.get("excluded_prior_match_ids")
        return (actual_hashes == cohort.get("source_sha256"), reproducible)

    def api_ledger_stats(self, bronze):
        path = bronze / "api-ledger.jsonl"
        rows = _ledger_requests(self.files.read_ledger(path))
        network = [row for row in rows if not row.get("cache_hit", False)]
        counts = Counter((row.get("session_id") for row in network))
        times = [
            datetime.fromisoformat(row["requested_at"])
            for row in network
            if row.get("requested_at")
        ]
        gaps = [(right - left).total_seconds() for left, right in zip(times, times[1:])]
        result = {
            "network_calls": len(network),
            "max_calls_per_session": max(counts.values(), default=0),
            "minimum_interval_s": min(gaps, default=None),
        }
        if any((row.get("schema_version") == 2 for row in rows)):
            uncertain = sum((row.get("phase") == "reserved" for row in network))
            result.update(
                request_budget_used=len(network),
                uncertain_requests=uncertain,
                completed_requests=len(network) - uncertain,
            )
        return result

    def _v3_manifest(self, run_id, protocol, artifacts, checks):
        manifest = {
            "schema_version": 1,
            "dataset_version": "v3",
            "run_id": run_id,
            "protocol_version": protocol["protocol_version"],
            "generated_at": self.utc_now(),
            "artifacts": sorted(artifacts, key=lambda row: row["path"]),
            "quality": _quality(checks),
        }
        self.files.write_json(self.paths.manifests / "v3" / f"{run_id}.json", manifest, indent=2)
        return manifest

    def evaluate_run(self, run_id):
        bronze, silver, gold = self.run_paths(run_id)
        protocol = self.ensure_protocol(bronze)
        protocol_version = protocol["protocol_version"]
        rule_protocol = protocol.get("rule_protocol_version", LEGACY_RULE_PROTOCOL_VERSION)
        cohort_path = silver / "cohort.json"
        if not self.files.exists(cohort_path):
            raise SystemExit("먼저 v3 init 실행 필요")
        cohort = json.loads(self.files.read_text(cohort_path, encoding="utf-8"))
        preflight_path = silver / "preflight.json"
        preflight = self._write_preflight(cohort, silver)
        candidates = candidate_matches(cohort)
        identities = self._identities(bronze, cohort["season_id"], protocol_version)
        source_hashes_match, cohort_reproducible = self._snapshot_consistency(
            cohort, bronze, protocol
        )
        api_stats = self.api_ledger_stats(bronze)
        observations, data_errors, parsed_paths, parsed_counts = ([], [], [], {})
        pseudonymous_errors = 0
        for row in candidates:
            match_id = row["match_id"]
            cache = self._match_cache(bronze, match_id)
            if not self.files.exists(cache):
                continue
            match = json.loads(self.files.read_text(cache, encoding="utf-8"))
            attrs = match["data"]["attributes"]
            if attrs.get("gameMode") != "squad-fpp" or not self._has_telemetry(bronze, match_id):
                continue
            parsed = self.pipeline.parse_match(
                match_id, version="v3", run_id=run_id, rule_protocol=rule_protocol
            )
            identity = identities[row["player_key"]]
            try:
                try:
                    measure = r2_observation(parsed["players"], account_id=identity["account_id"])
                except ValueError:
                    measure = r2_observation(parsed["players"], name=identity["name"])
            except ValueError as error:
                data_errors.append({"match_id": match_id, "error": str(error)})
                continue
            parsed_path = silver / "parsed" / f"{match_id}.json"
            pseudonymous = _pseudonymous_parsed(parsed, run_id)
            pseudonymous_errors += int(len(pseudonymous["players"]) != len(parsed["players"]))
            pseudonymous_errors += sum(
                (
                    not re.fullmatch("[0-9a-f]{24}", key) or "account_id" in player
                    for key, player in pseudonymous["players"].items()
                )
            )
            self.files.write_json(parsed_path, pseudonymous)
            parsed_paths.append(parsed_path)
            parsed_counts[match_id] = len(pseudonymous["players"])
            observations.append(
                {
                    "observation_id": digest(protocol_version, match_id, row["player_key"])[:24],
                    **row,
                    "rule_protocol_version": rule_protocol,
                    "season_id": cohort["season_id"],
                    "mode": attrs.get("gameMode"),
                    "map": attrs.get("mapName"),
                    **measure,
                    "skip_reason": None if measure["status"] == "evaluated" else measure["status"],
                }
            )
        observation_path = silver / "observations.json"
        self.files.write_json(observation_path, observations, indent=1)
        error_path = silver / "data-errors.json"
        self.files.write_json(error_path, data_errors, indent=1)
        collection = self.collection_summary(cohort, bronze)
        self.files.write_json(silver / "collection.json", collection, indent=2)
        checks = _v3_checks(
            cohort,
            candidates,
            observations,
            collection,
            data_errors,
            identities,
            pseudonymous_errors,
            source_hashes_match,
            cohort_reproducible,
            api_stats,
            preflight,
            rule_protocol,
        )
        quality = _quality(checks)
        result = None
        if quality["status"] == "PASS":
            evaluated = [row for row in observations if row["status"] == "evaluated"]
            holdout = [row for row in evaluated if row["split"] == "holdout"]
            by_player = defaultdict(list)
            for row in holdout:
                by_player[row["player_key"]].append(row)
            primary = [
                min(rows, key=lambda row: (row["recent_index"], row["match_id"]))
                for rows in by_player.values()
            ]
            primary_signals = sum((row["review_candidate"] for row in primary))
            decision = primary_decision(primary_signals, len(primary))
            secondary = _rate_summary(holdout)
            secondary["player_cluster_bootstrap_95"] = cluster_bootstrap_interval(
                holdout, int(digest(protocol_version, run_id)[:16], 16)
            )
            result = {
                "protocol_version": protocol_version,
                "rule_protocol_version": rule_protocol,
                "run_id": run_id,
                "generated_at": self.utc_now(),
                "cohort": {
                    "season_id": cohort["season_id"],
                    "players": len(cohort["players"]),
                    "holdout_players": 100,
                    "source_reference_players": preflight["source_reference_players"],
                    "candidate_owner_players": preflight["candidate_owner_players"],
                    "known_prior_matches": len(cohort.get("excluded_prior_match_ids", ())),
                    "excluded_prior_references": cohort.get("prior_excluded_references", 0),
                },
                "denominators": {
                    "frozen_unique_references": len(candidates),
                    **collection,
                    "accepted_observations": len(observations),
                    "target_below_min_attacks": sum(
                        (row["status"] == "target_below_min_attacks" for row in observations)
                    ),
                    "match_pool_below_8": sum(
                        (row["status"] == "match_pool_below_8" for row in observations)
                    ),
                    "match_pool_below_signal_capable": sum(
                        (row["status"] == "match_pool_below_signal_capable" for row in observations)
                    ),
                    "evaluated": len(evaluated),
                },
                "primary": {
                    "unit": "first_evaluated_match_per_player",
                    "review_candidates": primary_signals,
                    "evaluated_players": len(primary),
                    "review_candidate_rate": primary_signals / len(primary) if primary else None,
                    "one_sided_95": {"lower": decision["lower"], "upper": decision["upper"]},
                    "guardrail": REVIEW_RATE_GUARDRAIL,
                    "conclusion": decision["status"],
                },
                "secondary": secondary,
                "by_rank_decile": _subgroups(holdout, "rank_decile"),
                "by_map": _subgroups(holdout, "map"),
                "by_player": _subgroups(holdout, "player_key"),
                "by_eligible_pool_size": _subgroups(holdout, "eligible_players"),
                "status_by_split": _status_groups(observations, "split"),
                "status_by_rank_decile": _status_groups(observations, "rank_decile"),
                "api": api_stats,
                "experiment_status": "COMPLETE"
                if len(primary) >= MIN_PRIMARY_PLAYERS
                and len(holdout) >= MIN_SECONDARY_OBSERVATIONS
                else "INTERMEDIATE",
                "threshold_changed": False,
                "human_review": "DEFERRED_UNTIL_USER_REQUEST",
            }
            self.files.write_json(gold / "validation.json", result, indent=2)
        artifacts = []
        event_counts = {
            path.stem: json.loads(self.files.read_text(path, encoding="utf-8")).get("event_count")
            for path in parsed_paths
        }
        for path in sorted(self.files.rglob(bronze, "*")):
            if self.files.is_file(path):
                if path.parent.name == "telemetry":
                    match_id = path.name[:-8] if path.name.endswith(".json.gz") else path.name[:-5]
                    records = event_counts.get(match_id)
                    encoding = "gzip" if path.suffix == ".gz" else "json"
                elif path.suffix == ".jsonl":
                    records = sum(
                        (
                            1
                            for line in self.files.read_text(path, encoding="utf-8").splitlines()
                            if line.strip()
                        )
                    )
                    encoding = None
                else:
                    records, encoding = (1, None)
                artifacts.append(
                    self.medallion._artifact(
                        path, "bronze", path.parent.name, records, source_encoding=encoding
                    )
                )
        cohort_sources = [
            bronze / "api" / "seasons.json",
            bronze / "api" / "leaderboard.json",
            *sorted(self.files.glob(bronze / "api" / "players", "*.json")),
        ]
        _, _, prior_paths = self.prior_exposure(protocol_version, run_id)
        frozen_prior_hashes = set(protocol.get("prior_selection_sha256", {}).values())
        cohort_sources.extend(
            (path for path in prior_paths if self.files.hash(path) in frozen_prior_hashes)
        )
        artifacts.append(
            self.medallion._artifact(
                cohort_path,
                "silver",
                "frozen_cohort",
                len(cohort["players"]),
                tuple(cohort_sources),
            )
        )
        artifacts.append(
            self.medallion._artifact(
                preflight_path, "silver", "cohort_coverage_preflight", 1, (cohort_path,)
            )
        )
        artifacts.append(
            self.medallion._artifact(
                silver / "collection.json",
                "silver",
                "collection_state",
                1,
                tuple(
                    (
                        self._match_cache(bronze, row["match_id"])
                        for row in candidates
                        if self.files.exists(self._match_cache(bronze, row["match_id"]))
                    )
                ),
            )
        )
        artifacts.append(
            self.medallion._artifact(
                observation_path, "silver", "r2_observations", len(observations), parsed_paths
            )
        )
        artifacts.append(
            self.medallion._artifact(
                error_path, "silver", "data_errors", len(data_errors), parsed_paths
            )
        )
        for path in parsed_paths:
            match_id = path.stem
            telemetry = next(
                (
                    bronze / "telemetry" / f"{match_id}{suffix}"
                    for suffix in (".json.gz", ".json")
                    if self.files.exists(bronze / "telemetry" / f"{match_id}{suffix}")
                )
            )
            artifacts.append(
                self.medallion._artifact(
                    path, "silver", "parsed_players", parsed_counts[match_id], (telemetry,)
                )
            )
        if result is not None:
            artifacts.append(
                self.medallion._artifact(
                    gold / "validation.json",
                    "gold",
                    "holdout_validation",
                    1,
                    (observation_path, cohort_path),
                )
            )
        manifest = self._v3_manifest(run_id, protocol, artifacts, checks)
        if manifest["quality"]["status"] != "PASS":
            raise RuntimeError(
                f"v3 데이터 품질 게이트 FAIL: {manifest['quality']['error_count']} ERROR"
            )
        self.medallion.verify_artifacts(manifest)
        self.emit(
            f"v3 evaluate: {result['experiment_status']} primary={result['primary']['evaluated_players']} secondary={result['secondary']['evaluated']} DQ=PASS"
        )
        return result
