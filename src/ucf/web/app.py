"""FastAPI application factory for the UCF web dashboard.

@implements("use-cases/browse-spec-catalog")
@implements("use-cases/inspect-spec-detail")
@implements("use-cases/explore-dependency-graph")
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ucf.graph.dependency import DependencyGraph
from ucf.parser.loader import SpecLoader
from ucf.parser.registry import SpecRegistry
from ucf.web.api import init_registry, router


def create_app(
    specs_dir: Path,
    static_dir: Path | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="UCF Dashboard",
        version="0.1.0",
        description="Use Case Framework — spec catalog, dependency graph, and analysis",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    loader = SpecLoader(specs_dir)
    loaded, errors = loader.load_all_tolerant()

    registry = SpecRegistry()
    for path, spec in loaded:
        registry.register(spec, path)

    graph = DependencyGraph(registry)

    init_registry(registry, graph)

    app.include_router(router)

    if static_dir and static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
