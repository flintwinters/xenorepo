# Common Room

Common Room is a standalone anonymous group-chat application. FastAPI serves
the complete browser interface, synchronizes durable history, and broadcasts
new messages over WebSockets.

The frontend is a strict modular Lit graph. Its entrypoint only registers and
mounts the room component; app-owned modules retain message contracts,
reconnecting transport, and responsive styling. Shells, rails, panes, command
buttons, status indicators, and empty states come from the central Lit UI
package, and esbuild still produces one self-contained `dist/index.html`.

Application-owned runtime data is stored in the visible `data/` directory.
The default SQLite database is `data/chat.db`; set `CHAT_DATABASE_URL` to use a
different SQLAlchemy-compatible database.

From the central repository, build, validate, and serve this app with:

```console
python manage.py check
python manage.py chat serve
```

Run `python manage.py chat test` for the app-owned Python suite and
`python manage.py chat ui-check` for universal wide/narrow browser proof plus
the app-owned durable live-message journey.
