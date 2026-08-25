# Calculation Control

Calculation Control is a standalone, browser-based calculator with standard
and scientific modes, memory registers, keyboard controls, and a local
operation ledger. Its interface and state run entirely in the browser; the
ledger and calculator state are retained in the browser's local storage.

FastAPI serves the self-contained application from a single process. There is
no separate frontend development or production server.

From the repository root:

```console
python manage.py check
python manage.py calculator serve
```

Run `python manage.py calculator test` for the app-owned Python suite and
`python manage.py calculator ui-check` for universal wide/narrow browser proof.

Use the on-screen controls or the number keys, `+`, `-`, `*`, `/`, decimal
point, `Enter` (or `=`), and `Esc` to operate the calculator.
