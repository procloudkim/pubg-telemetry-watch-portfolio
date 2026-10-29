"""CLI arguments and compatibility output."""

import argparse
from .research_composition import pipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match")
    a = ap.parse_args()
    pipeline().detect(a.match)
