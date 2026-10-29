"""Compose file-based pipelines; imports have no file or network side effects."""

from src.adapters.files import ROOT, LocalFiles
from src.adapters.clock import SystemClock
from src.adapters.environment import Environment
from src.adapters.http import PubgHttp
from src.adapters import presentation
from src.application.workspace import Workspace
from src.application.medallion import Medallion
from src.application.pipeline import Pipeline
from src.application.collection import Collection
from src.application.research import Research


def workspace():
    return Workspace(ROOT)


def medallion():
    paths = workspace()
    return Medallion(LocalFiles(paths.root), paths, SystemClock())


def pipeline():
    service = medallion()
    return Pipeline(service.files, service.paths, service.clock, service, presentation, print)


def collection():
    service = pipeline()
    return Collection(
        service.files,
        service.paths,
        service.clock,
        PubgHttp(service.files, service.paths),
        service,
        print,
    )


def research():
    service = collection()
    return Research(
        service.files,
        service.paths,
        service.clock,
        service.http,
        Environment(),
        service.pipeline,
        service.pipeline.medallion,
        print,
    )
