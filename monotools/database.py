"""Shared SQLAlchemy construction with portable SQLite correctness defaults."""

from collections.abc import Callable
import os
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from monotools.orm import ClientProvenanceColumns


DatabasePreparation = Callable[[Engine], None]


class ClientProvenanceMixin(ClientProvenanceColumns):
    """Compatibility import for the canonical client-provenance template."""


def _enable_sqlite_foreign_keys(connection: Any, _record: Any) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_session_factory(
    database_url: str,
    metadata: MetaData,
    prepare: DatabasePreparation | None = None,
) -> sessionmaker[Session]:
    """Create a configured engine, schema, and session factory for an app."""
    sqlite = database_url.startswith("sqlite")
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if sqlite else {},
    )
    if sqlite:
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    metadata.create_all(engine)
    if prepare is not None:
        prepare(engine)
    return sessionmaker(engine, expire_on_commit=False)


def sqlite_url(path: Path) -> str:
    """Return a SQLite URL after ensuring its visible data directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def resolve_database_url(
    configured_url: str | None,
    environment_key: str,
    default_path: Path,
) -> str:
    """Resolve an app database from explicit, environment, then local sources."""
    return configured_url or os.environ.get(environment_key) or sqlite_url(default_path)
