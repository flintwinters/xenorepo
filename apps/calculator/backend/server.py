"""Single FastAPI runtime for the calculator application."""

from monotools.runtime import create_application


app = create_application("calculator")
