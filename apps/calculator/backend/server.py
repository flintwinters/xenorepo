"""Single FastAPI runtime for Calculator."""

from monotools.runtime.application import create_application


app = create_application("calculator")
