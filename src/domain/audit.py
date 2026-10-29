"""Compare SQL read models with frozen Gold; no database access."""


def _cross_check(summary, validation, manifest):
    funnel = summary["funnel"]
    denominators = validation.get("denominators") or {}
    primary = summary["primary"]
    gold_primary = validation.get("primary") or {}
    gold_secondary = validation.get("secondary") or {}
    checks = {
        "accepted_observations": funnel["accepted_observations"]
        == denominators.get("accepted_observations"),
        "evaluated": funnel["evaluated"]
        == denominators.get("evaluated")
        == gold_secondary.get("evaluated"),
        "target_below_min_attacks": funnel["target_below_min_attacks"]
        == denominators.get("target_below_min_attacks"),
        "match_pool_below_8": funnel["match_pool_below_8"]
        == denominators.get("match_pool_below_8"),
        "match_pool_below_signal_capable": (
            funnel["match_pool_below_signal_capable"]
            == denominators.get("match_pool_below_signal_capable")
        ),
        "secondary_review_candidates": funnel["review_candidates"]
        == gold_secondary.get("review_candidates"),
        "primary_evaluated_players": primary["evaluated_players"]
        == gold_primary.get("evaluated_players"),
        "primary_review_candidates": primary["review_candidates"]
        == gold_primary.get("review_candidates"),
        "managed_artifacts": summary["lineage"]["managed_artifacts"] == len(manifest["artifacts"]),
        "lineage_edges": summary["lineage"]["lineage_edges"]
        == sum(len(row.get("derived_from", ())) for row in manifest["artifacts"]),
        "lineage_acyclic": summary["lineage"]["cyclic"] == 0,
    }
    sql_maps = {
        key: (row["evaluated"], row["review_candidates"]) for key, row in summary["maps"].items()
    }
    gold_maps = {
        key: (row["evaluated"], row["review_candidates"])
        for key, row in (validation.get("by_map") or {}).items()
    }
    checks["map_groups"] = sql_maps == gold_maps
    sql_deciles = {
        key: (row["evaluated"], row["review_candidates"])
        for key, row in summary["deciles"].items()
        if row["evaluated"]
    }
    gold_deciles = {
        key: (row["evaluated"], row["review_candidates"])
        for key, row in (validation.get("by_rank_decile") or {}).items()
    }
    checks["rank_decile_groups"] = sql_deciles == gold_deciles
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"SQL과 Gold 교차검증 실패: {', '.join(failed)}")
    return [{"id": name, "status": "PASS"} for name in checks]
