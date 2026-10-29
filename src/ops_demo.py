"""Compatibility exports for synthetic demos and the process benchmark."""

from .domain.synthetic import r2_fixture, load_matches, compare_results
from .adapters.synthetic import write_inputs
from .adapters.sqlite_benchmark import synthetic_results
from .cli.demo_composition import demo
from .cli.ops_demo import main
from tools.ops_benchmark import benchmark, timed_cli


if __name__ == "__main__":
    main()
