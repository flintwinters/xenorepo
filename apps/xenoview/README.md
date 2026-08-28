# Xenorepo Cockpit

An evidence-first command-and-control view of Xenorepo's maintained footprint, Monotools modules, declared architecture, and explicit historical snapshots.

## Standalone deployment

From the repository root, restore and build the locked environment with `uv run manage.py bootstrap` and `uv run manage.py xenoview build`. Start the FastAPI service with `uv run manage.py xenoview start`; it serves the self-contained client and API on the reported local address.

Snapshots default to `apps/xenoview/data/xenoview.db`. Set `XENOVIEW_DATABASE_URL` to a PostgreSQL-compatible SQLAlchemy URL for another deployment. The service must run with read access to the Xenorepo working tree being observed. Snapshot creation is the only product mutation and never modifies repository source.
