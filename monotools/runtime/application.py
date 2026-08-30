"""Construct FastAPI runtimes for managed applications.

This module mounts health metadata and server-owned routes for declared,
self-contained frontend artifacts while leaving domain endpoints app-owned.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from monotools.orchestration.apps import get_app

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


def create_application(app_name: str) -> FastAPI:
    """Create an app with platform health and metadata-declared documents."""
    definition = get_app(app_name)
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
