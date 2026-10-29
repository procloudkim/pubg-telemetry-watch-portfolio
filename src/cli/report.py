"""CLI arguments and compatibility output."""

import argparse
from .research_composition import pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--match")
    args = parser.parse_args()
    pipeline().report(args.match)
