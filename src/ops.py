"""Compatibility entry point for local operations; see src.application.operations."""

from .domain.errors import OpsError
from .domain.operations import PROTOCOLS, MEASURE_FIELDS, STATES
from .domain.review import REVIEW_STATES
from .adapters.files import ROOT
from .adapters.environment import fingerprint, runtime, peak_rss_kib
from .adapters.sqlite_ops import SQL_PATH, connect, writer_lock, sql_measures
from .adapters.batch_inputs import read_inputs
from .adapters.clock import SystemClock
from .cli.ops_composition import (
    DEFAULT_STATE,
    register,
    recover,
    work,
    status,
    run_batch,
    retry_job,
    report_batch,
    review_list,
    review_show,
    review_change,
)
from .cli.ops import main


def utc_now():
    return SystemClock().now()


if __name__ == "__main__":
    raise SystemExit(main())
