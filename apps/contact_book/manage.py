"""Contact Book lifecycle manager and repeatable sample-data command."""

from pathlib import Path

import typer

from apps.contact_book.backend.database import Base, ContactStore
from apps.contact_book.backend.seeding import seed_contacts
from monotools.orchestration.management import create_app_manager
from monotools.persistence.database import create_session_factory


manager = create_app_manager(__file__)
app = manager.app


@app.command()
def seed(count: int = typer.Option(500, min=1, max=100_000)) -> None:
    """Populate deterministic contacts without duplicating previous generated records."""
    database = Path(__file__).parent / "data" / "contacts.db"
    sessions = create_session_factory(f"sqlite:///{database}", Base.metadata)
    created = seed_contacts(ContactStore(sessions), count)
    typer.echo(f"Seeded {created} contacts ({count - created} already present).")


if __name__ == "__main__":
    app()
