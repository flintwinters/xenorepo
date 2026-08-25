# Worminal

A browser window-manager environment for real localhost shell terminals,
delivered by the repository's FastAPI runtime. Each tab owns an independent
pseudo-terminal and login shell process on the machine running Worminal, while
windows are movable containers for one or more tabs. xterm.js provides ANSI/VT
rendering, keyboard input, scrollback, and terminal resizing.

The declared `frontend/index.ts` is only the registration and mount boundary.
App-owned modules separate workspace payload types, shortcut policy, HTTP
access, terminal-session resources, Worminal styling constants, and desktop
coordination. Monotools follows and strictly validates this complete graph, then
esbuild embeds it and xterm's CSS into the same self-contained `dist/index.html`.

## Run

From the repository root:

```console
python manage.py worminal serve
```

`python manage.py worminal test` owns the Python regressions. `python manage.py
worminal ui-check` composes universal browser proof with the app-owned desktop
suite; mocked WebSocket and synthetic context-menu checks are integration
evidence, not trusted physical-device claims.

Use `--watch` for a long-running development service. Monotools rebuilds the
Worminal document when files anywhere in its frontend tree or the central Lit
UI source tree are added, removed, or changed; Uvicorn
continues serving the rebuilt `dist/index.html` without a backend restart.

The included `worminal.service` runs this mode as a user-level systemd service.
Install it in `~/.config/systemd/user/`, enable it for `default.target`, and
enable user lingering when it must start at machine boot before login. The unit
binds `0.0.0.0:80` through `authbind`; grant the Worminal user execute access to
`/etc/authbind/byport/80` to authorize only that user and port.

Open `http://127.0.0.1:8000/worminal`, then create, drag, resize, minimize,
maximize, and close shell windows from the browser desktop. Use `+` in a window
titlebar to open another terminal tab. Drag tabs between windows or release a
tab elsewhere on the desktop to break it into a separate window. Closing a tab
terminates that shell; closing a window terminates all of its shells.

## LAN access

Worminal can bind to every network interface, but a real shell must never be
available without authentication. Set a long random password; the browser asks
for it once and retains only an HTTP-only session cookie:

```console
export WORMINAL_ACCESS_TOKEN="$(openssl rand -hex 32)"
uv run python manage.py worminal serve --host 0.0.0.0 --port 8000
```

Open `http://<server-lan-address>:8000/worminal`. For port 80, use your normal
privileged service or reverse-proxy setup; the same `WORMINAL_ACCESS_TOKEN`
requirement applies.

To run every terminal as a selected Unix account, add `--user`:

```console
uv run python manage.py worminal serve --host 0.0.0.0 --port 8000 --user alice
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
