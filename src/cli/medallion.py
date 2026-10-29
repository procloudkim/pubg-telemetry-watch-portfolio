"""Medallion command entry point."""

import argparse
from .research_composition import medallion


def main():
    service = medallion()
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions", nargs="+", choices=("v1", "v2"), default=("v1", "v2"))
    args = parser.parse_args()
    functions = {"v1": service.materialize_v1, "v2": service.materialize_v2}
    manifests = [functions[version]() for version in args.versions]
    for version in args.versions:
        service.verify_manifest(version)
    report_manifests = []
    for version in ("v1", "v2"):
        if service.files.exists(service.paths.manifests / f"{version}.json"):
            report_manifests.append(service.verify_manifest(version))
    service.write_quality_report(report_manifests)
    for manifest in manifests:
        print(
            f"Medallion {manifest['dataset_version']}: {manifest['quality']['status']} artifacts={len(manifest['artifacts'])}"
        )
