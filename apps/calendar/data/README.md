# Calendar runtime data

`calendar.db` is the visible, ignored SQLite database created by the standard lifecycle. Automated checks use named databases in this directory and remove them after use. Set `CALENDAR_DATABASE_URL` to use another SQLAlchemy database URL.
