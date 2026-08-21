# Worminal

A browser window-manager environment for real localhost shell terminals,
delivered by the repository's FastAPI runtime. Each window owns an independent
pseudo-terminal and login shell process on the machine running Worminal. xterm.js
provides ANSI/VT rendering, keyboard input, scrollback, and terminal resizing.

## Run

From the repository root:

```console
python manage.py serve worminal
```

Open the reported local URL, then create, drag, resize, minimize, maximize, and
close shell windows from the browser desktop. Closing a window or browser
connection terminates its shell process.

## Security boundary

Worminal intentionally grants shell access to the local user account running
the FastAPI process. The WebSocket rejects non-loopback clients and cross-origin
browsers. Keep the service bound to `127.0.0.1`; do not expose it through a
public bind address or reverse proxy.
