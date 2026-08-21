# Worminal

A browser-resident Python REPL delivered by the repository's FastAPI runtime.
Python runs inside a dedicated Web Worker through Pyodide; commands never run
on the FastAPI host. The first session requires network access to download the
Pyodide runtime from its pinned CDN URL. Browsers may cache it for later use.

## Run

From the repository root:

```console
python manage.py serve worminal
```

Open the reported local URL. Press Enter to execute, Shift+Enter for a newline,
Up/Down for history, and Ctrl+L to clear the transcript. `await` is supported at
the top level. Refreshing the page creates a clean Python interpreter.

This is intentionally a Python REPL rather than a host shell. It has the
browser sandbox's virtual filesystem and network restrictions and cannot run
server commands or access server files.
