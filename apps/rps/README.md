# Rock Paper Scissors

[Xenorepo on GitHub](https://github.com/flintwinters/xenorepo)

Rock Paper Scissors is a standalone live competitive arena. Guests enter a
streak-aware queue, receive simultaneous concealed ten-second rounds, and may
recover an interrupted match for five seconds through their durable guest
credential. Ranked decisive results and forfeits update competitive streaks;
five consecutive ties end in a draw.

FastAPI serves the self-contained browser document, JSON session API, and the
same-origin `/ws` arena protocol from one process. The
default SQLite database is `data/rps.db`; set `RPS_DATABASE_URL` to another
SQLAlchemy-compatible URL when deploying.

From the repository root:

```console
python manage.py check
python manage.py rps serve
```

`python manage.py rps ui-check` composes universal route proof with the
app-owned arena acceptance suite at factual wide and narrow Chromium viewports.
