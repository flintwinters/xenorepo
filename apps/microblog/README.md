# WIRE/98

WIRE/98 is a standalone public microblog. Visitors can read the newest-first
feed, create an account, publish posts of up to 280 characters, and record
durable like and unlike transitions.

FastAPI serves both the JSON API and the complete self-contained browser
interface. SQLAlchemy stores normalized domain state in `data/microblog.db` by
default. Set `MICROBLOG_DATABASE_URL` to select another SQLAlchemy-compatible
database.

From the repository root:

```console
python manage.py check
python manage.py test
python manage.py microblog serve
```

The leaf `test` command runs only this app's suite. `python manage.py microblog
ui-check` runs the universal wide/narrow browser contract.
