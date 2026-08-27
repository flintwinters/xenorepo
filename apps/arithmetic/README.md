# Calculator

A responsive, keyboard-friendly four-function calculator built as a strict
Lit monoapp. It supports chained operations, decimal input, sign changes,
percent conversion, correction, and clear error recovery.

Use the repository cockpit for every lifecycle operation:

```console
python manage.py check arithmetic
python manage.py test arithmetic
python manage.py ui-check arithmetic
python manage.py start arithmetic
```

The app builds to a self-contained document in `dist/` and is served by its
single FastAPI runtime.
