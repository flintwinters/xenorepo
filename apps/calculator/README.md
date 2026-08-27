# Calculator

A responsive, keyboard-friendly four-function calculator built as a strict
Lit monoapp. It supports chained operations, decimal input, sign changes,
percent conversion, correction, and clear error recovery.

Use the repository cockpit for every lifecycle operation:

```console
python manage.py calculator check
python manage.py calculator test
python manage.py calculator ui-check
python manage.py calculator serve
```

The app builds to a self-contained document in `dist/` and is served by its
single FastAPI runtime.
