"""CLI arguments and compatibility output."""

import argparse
from src.domain.pubg.parsing import RULE_PROTOCOLS, RULE_PROTOCOL_VERSION
from .research_composition import pipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match")
    ap.add_argument("--rule-protocol", choices=RULE_PROTOCOLS, default=RULE_PROTOCOL_VERSION)
    a = ap.parse_args()
    pipeline().parse(a.match, a.rule_protocol)
