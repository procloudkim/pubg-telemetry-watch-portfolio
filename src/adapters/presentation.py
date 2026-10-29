"""Byte-compatible Markdown presentation of verified read models."""

from collections import Counter
import json

RULE_KO = {
    "R1_speed": "도보 이동속도 상한 초과 (차량 구간 제외)",
    "R2_hit_ratio": "유효 피해 이벤트·공격 프록시가 매치 분포 대비 이상치",
    "R3_kill_burst": "행동 시각 기준 짧은 시간 내 다수 킬",
}


def render_review(signals, manifest, generated_at):
    modes = Counter((m.get("mode") or "unknown") for m in manifest)
    maps = Counter((m.get("map") or "unknown") for m in manifest)
    counts = lambda values: (
        ", ".join(f"`{name}` {count}판" for name, count in sorted(values.items())) or "없음"
    )
    lines = [
        "# Review Queue — 이상 플레이 신호",
        "## 표본 구성",
        f"- 매치 수: **{len(manifest)}판**",
        f"- 모드: {counts(modes)}",
        f"- 맵: {counts(maps)}",
        "",
        f"생성: {generated_at} · 신호 {len(signals)}건",
        "",
        "> 이 목록은 검토 후보다. 자동 확정이 아니며, 오탐을 전제로 사람이 근거를 확인한다.",
        "",
    ]
    if not signals:
        lines.append("신호 없음 — 수집된 매치에서 룰 임계값을 넘는 패턴이 없었다.")
    for i, s in enumerate(sorted(signals, key=lambda x: (x["match_id"], x["rule"])), 1):
        lines += [
            f"## {i}. [{s['rule']}] pla***",
            f"- 매치: `{s['match_id']}`",
            f"- 룰: {RULE_KO.get(s['rule'], s['rule'])} — 관측값 **{s['value']}** / 기준 {s['threshold']}",
            f"- 근거 이벤트: `{json.dumps(s['evidence'], ensure_ascii=False)}`",
        ]
        if s.get("victim_type_stratum"):
            lines.append(f"- 대상 유형 층: `{s['victim_type_stratum']}`")
        lines += ["- 판정: **REVIEW** (사람 확인 대기)", ""]
    return "\n".join(lines).encode()


def render_operations(batch_id, summary):
    groups, failures = summary["groups"], summary["failures"]
    lines = [
        "# Local batch operations",
        "",
        f"Batch: `{batch_id}`",
        "",
        f"Complete: `{summary['complete']}` · protocol: `{summary['rule_protocol']}`",
        "",
        "## Processing",
        "",
        "| State | Jobs |",
        "|---|---:|",
    ]
    lines += [f"| {key} | {value} |" for key, value in summary["counts"].items()]
    lines += ["", "## Metrics", "", "| Metric | Value |", "|---|---:|"]
    lines += [f"| {key} | {value} |" for key, value in summary["metrics"].items()]
    lines += [
        "",
        "## R2 denominators",
        "",
        "| Map | Mode | Status | Player-matches | REVIEW candidates |",
        "|---|---|---|---:|---:|",
    ]
    lines += [
        f"| {r['map_name']} | {r['mode']} | {r['status']} | {r['player_matches']} | {r['review_candidates']} |"
        for r in groups
    ]
    lines += [
        "",
        "## Failed or interrupted attempts",
        "",
        "| Stage | Code | Attempts |",
        "|---|---|---:|",
    ]
    lines += [f"| {r['stage']} | {r['error_code']} | {r['attempts']} |" for r in failures]
    lines += [
        "",
        "## Provenance",
        "",
        f"Input manifest SHA-256: `{summary['manifest_sha256']}`",
        f"Implementation SHA-256: `{summary['code_sha256']}`",
        "",
        "Operational replay only. Counts describe player-matches, not an independent accuracy evaluation.",
        "Interrupted attempt duration is unknown; throughput uses measured attempts only.",
        "Attack/damage evidence: query combat_event by job_id and player_key; event_index identifies the Bronze array entry.",
    ]
    return "\n".join(lines).encode()
