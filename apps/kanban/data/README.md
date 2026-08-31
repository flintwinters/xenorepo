# Kanban data

This visible directory owns Kanban's local durable state and test evidence. `kanban.db` contains the
single board, workflow entities, archive state, and immutable activity history. `uploads/` contains
uploaded attachment bytes under generated names; the database retains their original names and
media types.

Both the database and uploads are ignored runtime data. Back them up and restore them together to
preserve attachment integrity. `ui-check/`, generated OpenAPI files, and test databases are
repeatable artifacts produced through the root `manage.py` lifecycle and are not product data.
