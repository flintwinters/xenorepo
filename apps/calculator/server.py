"""Single FastAPI runtime for the calculator application."""

from tooling.runtime import create_application


app = create_application("calculator")
