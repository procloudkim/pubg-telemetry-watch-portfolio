"""Compatibility entry point for the frozen research protocol."""

from .domain.research import (
    LEGACY_PROTOCOL_VERSION,
    PROTOCOL_VERSION,
    PREFLIGHT_VERSION,
    COHORT_SIZE,
    MATCHES_PER_PLAYER,
    API_INTERVAL_S,
    MIN_PRIMARY_PLAYERS,
    MIN_SECONDARY_OBSERVATIONS,
    REVIEW_RATE_GUARDRAIL,
    BOOTSTRAP_REPLICATES,
    split_players,
    make_cohort,
    candidate_matches,
    cohort_preflight,
    binomial_cdf,
    _cdf_root,
    clopper_pearson_one_sided,
    wilson_interval,
    cluster_bootstrap_interval,
    primary_decision,
    _rate_summary,
    _subgroups,
    _status_groups,
    _v3_checks,
)
from .domain.serialization import stable_json, digest
from .domain.tokens import TOKEN, validate_token
from .domain.ledger import _ledger_requests
from .domain.pubg.privacy import _pseudonymous_parsed
from .domain.errors import BudgetExhausted
from .application.research import ApiSession as ApplicationApiSession
from .cli.v3 import main
from .cli.research_composition import research


def utc_now():
    return research().utc_now()


class ApiSession(ApplicationApiSession):
    """Preserve the public constructor while supplying its external resources."""

    def __init__(self, global_ledger, run_ledger, session_id, limit):
        service = research()
        super().__init__(
            global_ledger,
            run_ledger,
            session_id,
            limit,
            files=service.files,
            clock=service.clock,
            http=service.http,
            environment=service.environment,
        )


def _read_ledger(path):
    return research().files.read_ledger(path)


def _append_ledger(path, row):
    return research().files.append_ledger(path, row)


def _write_preflight(cohort, silver):
    return research()._write_preflight(cohort, silver)


def _require_preflight(report):
    return research()._require_preflight(report)


def preflight_run(run_id):
    return research().preflight_run(run_id)


def run_paths(run_id):
    return research().run_paths(run_id)


def prior_exposure(protocol_version=PROTOCOL_VERSION, exclude_run_id=None):
    return research().prior_exposure(protocol_version, exclude_run_id)


def ensure_protocol(bronze):
    return research().ensure_protocol(bronze)


def init_run(run_id, session_id, api_call_limit):
    return research().init_run(run_id, session_id, api_call_limit)


def _match_cache(bronze, match_id):
    return research()._match_cache(bronze, match_id)


def _has_telemetry(bronze, match_id):
    return research()._has_telemetry(bronze, match_id)


def collection_summary(cohort, bronze):
    return research().collection_summary(cohort, bronze)


def collect_run(run_id, session_id, api_call_limit):
    return research().collect_run(run_id, session_id, api_call_limit)


def _identities(bronze, season_id, protocol_version):
    return research()._identities(bronze, season_id, protocol_version)


def _snapshot_consistency(cohort, bronze, protocol):
    return research()._snapshot_consistency(cohort, bronze, protocol)


def api_ledger_stats(bronze):
    return research().api_ledger_stats(bronze)


def _v3_manifest(run_id, protocol, artifacts, checks):
    return research()._v3_manifest(run_id, protocol, artifacts, checks)


def evaluate_run(run_id):
    return research().evaluate_run(run_id)


if __name__ == "__main__":
    main()
