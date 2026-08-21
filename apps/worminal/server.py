"""Single FastAPI runtime for the browser Python terminal."""

from monotools.runtime import create_application


app = create_application("worminal")
