"""Compatibility entry point; implementation is separated by responsibility."""

from .domain.pubg.parsing import (
    RULE_PROTOCOL_VERSION,
    LEGACY_RULE_PROTOCOL_VERSION,
    RULE_PROTOCOLS,
    ts,
    parse_events,
)
from .cli.parse import main
from .cli.research_composition import pipeline


def parse_match(match_id, *, version=None, run_id=None, rule_protocol=RULE_PROTOCOL_VERSION):
    return pipeline().parse_match(
        match_id, version=version, run_id=run_id, rule_protocol=rule_protocol
    )


if __name__ == "__main__":
    main()
