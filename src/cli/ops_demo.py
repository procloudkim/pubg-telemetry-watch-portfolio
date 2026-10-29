"""Benchmark command arguments."""

import argparse
from pathlib import Path
from tools.ops_benchmark import benchmark


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", type=int, nargs="*", default=[1000000, 10000000])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--real-manifest", type=Path, action="append", default=[])
    parser.add_argument("--match-events", type=int, default=40000)
    parser.add_argument("--compare-to", type=Path)
    args = parser.parse_args()
    if args.repeats < 1 or args.match_events < 1 or any(size < 1 for size in args.sizes):
        parser.error("sizes and repeats must be positive")
    benchmark(
        args.output,
        sizes=args.sizes,
        repeats=args.repeats,
        real_manifests=args.real_manifest,
        match_events=args.match_events,
        compare_to=args.compare_to,
    )
