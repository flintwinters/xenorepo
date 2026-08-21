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

Use `--watch` for a long-running development service. Monotools rebuilds the
Worminal document when its TypeScript or central Lit UI inputs change; Uvicorn
continues serving the rebuilt `dist/index.html` without a backend restart.

The included `worminal.service` runs this mode as a user-level systemd service.
Install it in `~/.config/systemd/user/`, enable it for `default.target`, and
enable user lingering when it must start at machine boot before login. The unit
binds `0.0.0.0:80`; install `worminal.sysctl` in `/etc/sysctl.d/` so the
unprivileged user service can bind port 80 without executable capabilities.

Open `http://127.0.0.1:8000/worminal`, then create, drag, resize, minimize, maximize, and
close shell windows from the browser desktop. Closing a window or browser
connection terminates its shell process.

## LAN access

Worminal can bind to every network interface, but a real shell must never be
available without authentication. Set a long random password; the browser asks
for it once and retains only an HTTP-only session cookie:

```console
export WORMINAL_ACCESS_TOKEN="$(openssl rand -hex 32)"
uv run python manage.py serve worminal --host 0.0.0.0 --port 8000
```

Open `http://<server-lan-address>:8000/worminal`. For port 80, use your normal
privileged service or reverse-proxy setup; the same `WORMINAL_ACCESS_TOKEN`
requirement applies.

To run every terminal as a selected Unix account, add `--user`:

```console
uv run python manage.py serve worminal --host 0.0.0.0 --port 8000 --user alice
```

Selecting a different account requires the hosting service to run with the
necessary Unix privilege. Each terminal child drops to `alice` before its login
shell starts; an unavailable user or unauthorized switch fails at startup.

The access password can be changed from the top-right Settings panel. Password
changes persist in the database and revoke access cookies held by other browsers.

## Security boundary

Worminal intentionally grants shell access to the local user account running
the FastAPI process. Loopback clients work without a password. Non-loopback
clients require `WORMINAL_ACCESS_TOKEN` through the page's one-password prompt,
and the WebSocket rejects cross-origin browsers. Keep this service on a trusted
LAN or behind a secure reverse proxy; it is not a public Internet service.
