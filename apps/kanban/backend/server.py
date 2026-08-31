"""Single FastAPI runtime for Kanban Board."""

from monotools.runtime.application import create_application


app = create_application("kanban")
