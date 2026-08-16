"""Single FastAPI runtime for the calculator application."""

from pathlib import Path

from tooling.runtime import create_application


DIST = Path(__file__).parent / "dist"
app = create_application("Calculation Control", DIST / "index.html")
