"""Compatibility entry point; implementation is separated by responsibility."""

from .domain.quality import _check, _quality
from .cli.medallion import main
from .cli.research_composition import medallion


def _artifact(path, layer, dataset, records, derived_from=(), source_encoding=None):
    return medallion()._artifact(path, layer, dataset, records, derived_from, source_encoding)


def _telemetry_target(version, match_id, legacy):
    return medallion()._telemetry_target(version, match_id, legacy)


def _write_manifest(version, run_id, artifacts, checks, protocol_version):
    return medallion()._write_manifest(version, run_id, artifacts, checks, protocol_version)


def materialize_v1():
    return medallion().materialize_v1()


def materialize_v2():
    return medallion().materialize_v2()


def verify_manifest(version):
    return medallion().verify_manifest(version)


def verify_artifacts(manifest):
    return medallion().verify_artifacts(manifest)


def write_quality_report(manifests):
    return medallion().write_quality_report(manifests)


if __name__ == "__main__":
    main()
