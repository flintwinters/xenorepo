# Kanban runtime data

This visible directory owns ignored local runtime and verification state.

- `kanban.db` is the default development database.
- `test-kanban.db` is recreated by the Python suite.
- `ui-check/` contains the isolated browser database, service log, traces, and
  failure screenshots produced by `python manage.py kanban ui-check`.

No file in this directory is required to build the application.
