"""Compose the synthetic walkthrough from production use cases."""

from src.adapters.files import ROOT, LocalFiles
from src.adapters.environment import Environment
from src.adapters.synthetic import write_inputs
from src.application.demo import Demo
from .ops_composition import DEFAULT_STATE, run_batch, report_batch


def demo(state_dir=DEFAULT_STATE):
    return Demo(ROOT, LocalFiles(), Environment(), write_inputs, run_batch, report_batch).run(
        state_dir
    )
