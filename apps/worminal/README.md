# Worminal

A browser window-manager environment for independent Python terminals, delivered
by the repository's FastAPI runtime. One Pyodide engine runs inside a dedicated
module Web Worker while each terminal receives an isolated Python namespace;
commands never run on the FastAPI host. The first session requires network
access to download the pinned runtime. Browsers may cache it for later use.

## Run

From the repository root:

```console
python manage.py serve worminal
```

Open the reported local URL, then create, drag, resize, minimize, maximize, and
close terminal windows from the browser desktop. Press Enter to execute,
Shift+Enter for a newline, and Up/Down for each window's command history.
`await` is supported at the top level. Refreshing creates a clean workspace.

Runtime startup fails visibly after 30 seconds. Use **RETRY PYTHON** after
restoring network access instead of refreshing or waiting indefinitely.

This is intentionally a Python REPL rather than a host shell. It has the
browser sandbox's virtual filesystem and network restrictions and cannot run
server commands or access server files.
