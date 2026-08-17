"""Shared FastAPI application construction for managed applications."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from monotools.apps import get_app


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

    for route, artifact_name in definition.routes:
        endpoint = _document_endpoint(definition.dist_directory / definition.artifact(artifact_name).output)
        endpoint.__name__ = f"document_{artifact_name}"
        application.add_api_route(route, endpoint, methods=["GET"], response_class=FileResponse)
    return application
