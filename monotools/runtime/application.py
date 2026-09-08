"""Construct FastAPI runtimes for managed applications.

This module mounts health metadata and server-owned routes for declared,
self-contained frontend artifacts while leaving domain endpoints app-owned.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from monotools.orchestration.apps import AppDefinition, AppDefinitionError, get_app, load_app

AGENT_TOOLS_ROUTE = "/agent/tools"


def api_openapi_schema(application: FastAPI) -> dict[str, object]:
    """Return the live OpenAPI registry restricted to app-owned API routes."""
    schema = application.openapi()
    return {
        **schema,
        "paths": {
            path: value for path, value in schema.get("paths", {}).items()
            if path == "/api" or path.startswith("/api/")
        },
    }


def _document_endpoint(document: Path):
    def serve_document() -> Path:
        return document

    return serve_document


def _create_application(definition: AppDefinition) -> FastAPI:
    application = FastAPI(title=definition.title)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get(AGENT_TOOLS_ROUTE, include_in_schema=False)
    def agent_tools() -> dict[str, object]:
        return api_openapi_schema(application)

    for route, artifact_name in definition.routes:
        endpoint = _document_endpoint(definition.dist_directory / definition.artifact(artifact_name).output)
        endpoint.__name__ = f"document_{artifact_name}"
        application.add_api_route(route, endpoint, methods=["GET"], response_class=FileResponse)
    return application


def create_application(app_name: str) -> FastAPI:
    """Create an application selected by central metadata identity."""
    return _create_application(get_app(app_name))


def create_local_application(module_file: str | Path) -> FastAPI:
    """Create the application owned by an exact ``backend/server.py`` module."""
    source = Path(module_file).resolve()
    backend = source.parent
    if source.name != "server.py" or backend.name != "backend":
        raise AppDefinitionError(
            f"local application module must be an app-owned backend/server.py: {source}"
        )
    definition = load_app(backend.parent)
    expected = definition.backend_directory / "server.py"
    if source != expected.resolve():
        raise AppDefinitionError(
            f"local application module does not match {definition.module}: {source}"
        )
    return _create_application(definition)
