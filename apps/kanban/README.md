# Kanban Console

[Xenorepo on GitHub](https://github.com/flintwinters/xenorepo)

Kanban Console is a compact, durable single-board workflow application. It
supports card creation, renaming, ordering, movement, deletion, and linear
undo/redo history through one FastAPI service and a self-contained browser
artifact. A card's daily-review checkbox remains checked for 24 hours, then
automatically becomes unchecked and visually highlighted. The browser is a
strict Preact TSX application composed from Xenorepo's central typed UI
components; lifecycle,
builds, runtime documents, database setup, HTTP error
handling, and browser verification are owned by Monotools.

Opening a card exposes its timestamped activity log. Notes are append-only and
remain attached to the card through renames, moves, restarts, and delete/undo.

`python manage.py kanban ui-check` proves universal wide/narrow rendering plus
continuous trusted Chromium mouse and native-touch paths. It asserts the
network mutation, rendered destination, authoritative API state, and reload
persistence; successful input records and run summaries live in
`data/ui-check/`.

From a Xenorepo checkout, use the repository cockpit:

```console
python manage.py kanban check
python manage.py kanban test
python manage.py kanban ui-check
python manage.py kanban serve
```

The default SQLite database is `data/kanban.db`. Override it with a SQLAlchemy
URL in `KANBAN_DATABASE_URL` when deploying the app independently. Build output
is generated in `dist/` and is intentionally not committed.
