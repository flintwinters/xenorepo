"""Shared FastAPI application construction for managed applications."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse


def create_application(title: str, document: Path) -> FastAPI:
    """Create an app with the platform health and root-document contract."""
    application = FastAPI(title=title)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/", response_class=FileResponse)
    def index() -> Path:
        return document

    return application
