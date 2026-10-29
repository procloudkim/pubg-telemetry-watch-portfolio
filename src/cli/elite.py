"""CLI arguments and compatibility output."""

import argparse
from .research_composition import collection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-region", default="pc-as")
    parser.add_argument("--shard", default="steam")
    parser.add_argument("--mode", default="squad-fpp")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--matches-per-player", type=int, default=5)
    parser.add_argument("--api-call-limit", type=int, default=60)
    args = parser.parse_args()
    if (
        not 1 <= args.top <= 10
        or args.matches_per_player < 1
        or (not 3 <= args.api_call_limit <= 60)
    ):
        raise SystemExit(
            "--top은 1~10, --matches-per-player는 1 이상, --api-call-limit은 3~60이어야 함"
        )
    collection().elite(args)
