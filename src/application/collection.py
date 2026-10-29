"""Bounded v1/v2 collection; live requests occur only through the transport port."""

from .ports import Clock, Files, PubgTransport
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import quote
from src.domain.pubg.selection import (
    current_season,
    top_players,
    round_robin_matches,
    telemetry_url,
)
from src.domain.pubg.parsing import RULE_PROTOCOL_VERSION
from src.domain.pubg.detection import MIN_ATTACKS, Z_HIT, r2_observation

API_INTERVAL_S = 7


class Collection:
    def __init__(self, files: Files, paths, clock: Clock, http: PubgTransport, pipeline, emit):
        self.files, self.paths, self.clock = files, paths, clock
        self.http, self.pipeline, self.emit = http, pipeline, emit

    def match_ids_for_player(self, name, shard, raw_path=None):
        data = self.http.get(f"/shards/{shard}/players?filter[playerNames]={quote(name)}", raw_path)
        players = data.get("data", [])
        if not players:
            raise SystemExit(f"플레이어 없음: {name} (kakao 계정이면 --shard kakao)")
        return [m["id"] for m in players[0]["relationships"]["matches"]["data"]]

    def match_ids_sample(self, shard, raw_path=None):
        data = self.http.get(f"/shards/{shard}/samples", raw_path)
        return [m["id"] for m in data["data"]["relationships"]["matches"]["data"]]

    def fetch(self, options):
        run_id = datetime.fromisoformat(self.clock.now()).strftime("%Y%m%dT%H%M%S%fZ")
        api_dir = self.paths.bronze / "v1" / "api" / run_id
        source_path = api_dir / ("player.json" if options.player else "sample.json")
        ids = (
            self.match_ids_for_player(options.player, options.shard, source_path)
            if options.player
            else self.match_ids_sample(options.shard, source_path)
        )
        manifest = []
        for mid in ids[: options.limit]:
            self.clock.sleep(7)
            match = self.http.get(
                f"/shards/{options.shard}/matches/{mid}", api_dir / "matches" / f"{mid}.json"
            )
            attrs = match["data"]["attributes"]
            encoding = self.http.download_telemetry(telemetry_url(match), mid)
            manifest.append(
                {
                    "match_id": mid,
                    "map": attrs.get("mapName"),
                    "mode": attrs.get("gameMode"),
                    "duration_s": attrs.get("duration"),
                    "telemetry": encoding,
                }
            )
            self.emit(
                f"수집: {mid} map={attrs.get('mapName')} mode={attrs.get('gameMode')} telemetry={encoding}"
            )
        self.files.write_json(self.paths.silver / "v1" / "selection.json", manifest, indent=1)
        self.files.write_json(self.paths.data / "manifest.json", manifest, indent=1)

    def elite(self, options):
        calls = 0
        last_request = None
        api_run = datetime.fromisoformat(self.clock.now()).strftime("%Y%m%dT%H%M%S%fZ")
        api_dir = self.paths.bronze / "v2" / "api" / api_run

        def get(path, raw_path):
            nonlocal calls, last_request
            if calls >= options.api_call_limit:
                raise SystemExit(f"API 호출 예산 소진: {calls}/{options.api_call_limit}")
            if last_request is not None:
                self.clock.sleep(max(0, API_INTERVAL_S - (self.clock.monotonic() - last_request)))
            last_request = self.clock.monotonic()
            calls += 1
            return self.http.get(path, raw_path)

        season_id = current_season(
            get(f"/shards/{options.shard}/seasons", api_dir / "seasons.json")
        )
        leaderboard = get(
            f"/shards/{options.platform_region}/leaderboards/{season_id}/{options.mode}",
            api_dir / "leaderboard.json",
        )
        leaders = top_players(leaderboard, options.top)
        if len(leaders) != options.top:
            raise SystemExit(f"리더보드 인원 부족: {len(leaders)}/{options.top}")
        ids = [row["id"] for row in leaders]
        players = get(
            f"/shards/{options.shard}/players?filter[playerIds]={quote(','.join(ids), safe=',')}",
            api_dir / "players.json",
        )
        recent = {
            row["id"]: [
                match["id"]
                for match in row["relationships"]["matches"]["data"][: options.matches_per_player]
            ]
            for row in players.get("data", [])
        }
        candidates = round_robin_matches(
            {player_id: recent.get(player_id, []) for player_id in ids}, options.matches_per_player
        )
        selected = candidates[: options.api_call_limit - calls]
        if not selected:
            raise SystemExit("매치 API 호출 예산이 없음")
        names = {row["id"]: row["attributes"]["name"] for row in leaders}
        ranks = {row["id"]: row["attributes"]["rank"] for row in leaders}
        targets_by_match = defaultdict(list)
        for player_id in ids:
            for match_id in recent.get(player_id, []):
                if match_id in selected:
                    targets_by_match[match_id].append(player_id)
        ratios = []
        observed_ranks = set()
        current_rule_signals = 0
        current_rule_statuses = []
        manifest = []
        self.files.mkdir(self.paths.data, exist_ok=True)
        for index, match_id in enumerate(selected, 1):
            match = get(
                f"/shards/{options.shard}/matches/{match_id}",
                api_dir / "matches" / f"{match_id}.json",
            )
            attributes = match["data"]["attributes"]
            encoding = self.http.download_telemetry(telemetry_url(match), match_id, version="v2")
            parsed = self.pipeline.parse_match(match_id, version="v2")
            self.files.write_json(self.paths.silver / "v2" / "parsed" / f"{match_id}.json", parsed)
            self.files.write_json(self.paths.data / f"{match_id}.parsed.json", parsed)
            for player_id in targets_by_match[match_id]:
                try:
                    observation = r2_observation(parsed["players"], account_id=player_id)
                except ValueError:
                    try:
                        observation = r2_observation(parsed["players"], name=names[player_id])
                    except ValueError:
                        observation = {"status": "target_not_observed", "review_candidate": False}
                if observation.get("attacks", 0) >= MIN_ATTACKS:
                    ratios.append(observation["ratio"])
                    observed_ranks.add(ranks[player_id])
                current_rule_statuses.append(observation["status"])
                current_rule_signals += observation["review_candidate"]
            manifest.append(
                {
                    "match_id": match_id,
                    "map": attributes.get("mapName"),
                    "mode": attributes.get("gameMode"),
                    "duration_s": attributes.get("duration"),
                    "telemetry": encoding,
                }
            )
            self.emit(f"엘리트 수집: {index}/{len(selected)} telemetry={encoding}")
        if len(ratios) < 2:
            raise SystemExit(f"R2 기준선 표본 부족: {len(ratios)}")
        mean = statistics.mean(ratios)
        sd = statistics.pstdev(ratios)
        z_scores = [(ratio - mean) / sd if sd else 0.0 for ratio in ratios]
        reference_signals = sum((z > Z_HIT for z in z_scores))
        coverage = [
            sum((match_id in selected for match_id in recent.get(player_id, [])))
            for player_id in ids
        ]
        status_counts = Counter(current_rule_statuses)
        evaluated_observations = status_counts.pop("evaluated", 0)
        result = {
            "generated_at": datetime.fromisoformat(self.clock.now()).isoformat(timespec="seconds"),
            "rule_protocol_version": RULE_PROTOCOL_VERSION,
            "cohort": {
                "platform_region": options.platform_region,
                "season_id": season_id,
                "mode": options.mode,
                "leaderboard_players": len(leaders),
                "target_matches_per_player": options.matches_per_player,
                "matches_per_player_min": min(coverage),
                "matches_per_player_mean": round(statistics.mean(coverage), 2),
                "matches_per_player_max": max(coverage),
                "unique_matches": len(selected),
                "qualified_observations": len(ratios),
                "qualified_players": len(observed_ranks),
            },
            "elite_reference": {
                "ratio_mean": round(mean, 4),
                "ratio_sd": round(sd, 4),
                "ratios": [round(ratio, 4) for ratio in ratios],
                "current_threshold_z": Z_HIT,
                "max_observed_z": round(max(z_scores), 4),
                "signals": reference_signals,
                "review_candidate_rate": round(reference_signals / len(ratios), 4),
            },
            "current_match_rule": {
                "signals": current_rule_signals,
                "target_observations": len(current_rule_statuses),
                "evaluated_observations": evaluated_observations,
                "skipped_observations": len(current_rule_statuses) - evaluated_observations,
                "skipped_by_reason": dict(sorted(status_counts.items())),
                "review_candidate_rate": current_rule_signals / evaluated_observations
                if evaluated_observations
                else None,
                "denominator_status": "MEASURED",
            },
            "api_calls": calls,
            "threshold_changed": False,
        }
        self.files.write_json(self.paths.silver / "v2" / "selection.json", manifest, indent=1)
        self.files.write_json(self.paths.gold / "v2" / "baseline.json", result, indent=1)
        self.files.write_json(self.paths.data / "elite-manifest.json", manifest, indent=1)
        self.files.write_json(self.paths.data / "elite-baseline.json", result, indent=1)
        rate = result["current_match_rule"]["review_candidate_rate"]
        rate_text = f"{rate:.2%}" if rate is not None else "산출 불가"
        self.emit(
            f"엘리트 기준선: top{len(leaders)} 매치 {len(selected)}판 관측 {len(ratios)}건 R2 신호 {current_rule_signals}건 후보율 {rate_text} API {calls}회"
        )
