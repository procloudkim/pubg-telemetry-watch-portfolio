"""Compatibility entry point; implementation is separated by responsibility."""

from .domain.pubg.selection import current_season, top_players, round_robin_matches

API_INTERVAL_S = 7
from .cli.elite import main
from .cli.research_composition import collection


if __name__ == "__main__":
    main()
