# Rock Paper Scissors

Rock Paper Scissors is a standalone social arena. This checkpoint
provides durable guest identity and the complete ranked match state machine;
live matchmaking and round transport are introduced by the next checkpoint.

FastAPI serves the self-contained browser document and JSON session API. The
default SQLite database is `data/rps.db`; set `RPS_DATABASE_URL` to another
SQLAlchemy-compatible URL when deploying.

From the repository root:

```console
python manage.py check
python manage.py serve rps
```
