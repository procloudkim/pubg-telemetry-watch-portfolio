"""CLI arguments and compatibility output."""

import argparse
from .research_composition import collection


def main():
    p = argparse.ArgumentParser()
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--player")
    source.add_argument("--sample", action="store_true")
    p.add_argument("--shard", default="steam")
    p.add_argument("--limit", type=int, default=3)
    a = p.parse_args()
    if not 1 <= a.limit <= 59:
        raise SystemExit("--limit은 1~59 (선택 1회 포함 세션 60회 이하)")
    collection().fetch(a)
