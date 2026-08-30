"""Single FastAPI runtime for Waveform Synthesizer."""

from monotools.runtime.application import create_application


app = create_application("synthesizer")
