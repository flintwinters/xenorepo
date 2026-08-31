"""Single FastAPI runtime for Kanban."""

from monotools.runtime.application import create_application


app = create_application("kanban")
