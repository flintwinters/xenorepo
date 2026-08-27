# Calendar Console

Calendar Console is a single-user, month-first planner served as one self-contained Lit artifact by FastAPI. It stores single-day all-day and timed events in SQLite and fixes the calendar timezone from the first browser that opens it.

From a Xenorepo checkout, use the repository cockpit:

```console
.venv/bin/python manage.py calendar build
.venv/bin/python manage.py calendar test
.venv/bin/python manage.py calendar serve
```

As a standalone submodule with the same Python and Node dependencies available, `manage.py` exposes `build`, `check`, `test`, `ui-check`, and `serve`. Runtime state defaults to `data/calendar.db`; set `CALENDAR_DATABASE_URL` to override the SQLAlchemy URL.

The HTTP interface is documented in [SPEC.md](SPEC.md). Recurrence, synchronization, authentication, sharing, and timezone changes are outside this first product boundary.
