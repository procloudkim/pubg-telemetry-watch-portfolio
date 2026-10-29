"""Resource ownership and compatibility signatures for operations entry points."""

from contextlib import closing
from pathlib import Path

from src.adapters.files import ROOT, LocalFiles
from src.adapters.batch_inputs import BatchInputs
from src.adapters.clock import SystemClock
from src.adapters.environment import Environment
from src.adapters import presentation
from src.adapters.sqlite_ops import connect, writer_lock, SQLiteStore
from src.application.operations import Operations

DEFAULT_STATE = Path.home() / ".local/state/pubg-telemetry-watch"


def operations(connection):
    return Operations(
        SQLiteStore(connection),
        BatchInputs(),
        LocalFiles(),
        SystemClock(),
        Environment(),
        presentation,
    )


def run_batch(batch_id, manifest_path=None, *, state_dir=DEFAULT_STATE, source_root=ROOT):
    state_dir = Path(state_dir)
    with writer_lock(state_dir), closing(connect(state_dir)) as connection:
        service = operations(connection)
        if manifest_path is not None:
            service.register(batch_id, Path(manifest_path), Path(source_root))
        return service.work(batch_id)


def retry_job(batch_id, job_id, *, state_dir=DEFAULT_STATE):
    state_dir = Path(state_dir)
    with writer_lock(state_dir), closing(connect(state_dir)) as connection:
        return operations(connection).retry(batch_id, job_id)


def review_list(*, state_dir=DEFAULT_STATE, batch_id=None, state=None):
    with closing(connect(Path(state_dir), readonly=True)) as connection:
        return operations(connection).review_list(batch_id, state)


def review_show(case_id, *, state_dir=DEFAULT_STATE):
    with closing(connect(Path(state_dir), readonly=True)) as connection:
        return operations(connection).review_show(case_id)


def review_change(action, case_id, operator, *, note=None, state_dir=DEFAULT_STATE):
    state_dir = Path(state_dir)
    with writer_lock(state_dir), closing(connect(state_dir)) as connection:
        return operations(connection).review_change(action, case_id, operator, note)


def report_batch(batch_id, *, state_dir=DEFAULT_STATE):
    state_dir = Path(state_dir)
    with writer_lock(state_dir), closing(connect(state_dir, readonly=True)) as connection:
        return operations(connection).report(batch_id, state_dir / "reports" / batch_id)


def register(connection, batch_id, manifest_path, source_root=ROOT):
    return operations(connection).register(batch_id, manifest_path, source_root)


def work(connection, batch_id):
    return operations(connection).work(batch_id)


def recover(connection):
    return operations(connection).recover()


def status(connection, batch_id):
    return operations(connection).status(batch_id)
