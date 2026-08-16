"""Single FastAPI runtime for the calculator application."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse


DIST = Path(__file__).parent / "dist"
app = FastAPI(title="Calculation Control")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=FileResponse)
def index() -> Path:
    return DIST / "index.html"
