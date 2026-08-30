"""Single FastAPI runtime for Waveform Lab."""

from monotools.runtime.application import create_application


app = create_application("waveform_lab")
