# Kanban Console

Kanban Console is a compact, durable single-board workflow application. It
supports card creation, renaming, ordering, movement, deletion, and linear
undo/redo history through one FastAPI service and a self-contained browser
artifact. The browser is a Lit application composed from Xenorepo's central Lit
UI components; lifecycle, builds, runtime documents, database setup, HTTP error
handling, and browser verification are owned by Monotools.

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
