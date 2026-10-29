"""Compatibility entry point; implementation is separated by responsibility."""

from .domain.pubg.selection import telemetry_url
from .cli.fetch import main
from .cli.research_composition import collection


def match_ids_for_player(name, shard, raw_path=None):
    return collection().match_ids_for_player(name, shard, raw_path)


def match_ids_sample(shard, raw_path=None):
    return collection().match_ids_sample(shard, raw_path)


def download_telemetry(url, match_id, *, version="v1", run_id=None, compatibility_copy=True):
    return collection().http.download_telemetry(
        url, match_id, version=version, run_id=run_id, compatibility_copy=compatibility_copy
    )


if __name__ == "__main__":
    main()
