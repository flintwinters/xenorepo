"""Single FastAPI runtime for Waveform Lab."""

from monotools.runtime.application import create_local_application


app = create_local_application(__file__)
