"""Single FastAPI runtime for the quiz application."""

from monotools.runtime import create_application


app = create_application("quiz")
