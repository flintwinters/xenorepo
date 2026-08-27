"""Single FastAPI runtime for Calculator."""

from monotools.runtime import create_application


app = create_application("calculator")
