"""Assemble shared application infrastructure from declarative metadata.

This module resolves an app's clock, database URL, schema preparation, and
session factory into one typed context without absorbing application policy.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from sqlalchemy import MetaData
from sqlalchemy.orm import Session, sessionmaker

from monotools.apps import AppDefinition, get_app
from monotools.database import DatabasePreparation, create_session_factory, resolve_database_url
from monotools.identity import DatabaseSchema


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class AppContext:
    """The stable infrastructure boundary shared by an application."""

    def __init__(self, definition: AppDefinition, database_url: str | None = None,
        sessions: sessionmaker[Session] | None = None, clock: Clock | None = None) -> None:
        self.definition = definition
        self.database_url = database_url
        self.sessions = sessions
        self.clock = clock or SystemClock()

    def require_sessions(self) -> sessionmaker[Session]:
        if self.sessions is None:
            raise RuntimeError(f"{self.definition.name} does not declare database infrastructure")
        return self.sessions


def create_app_context(app_name: str, *, metadata: MetaData | None = None,
    schema: DatabaseSchema | None = None,
    default_database: Path | None = None, environment_key: str | None = None,
    database_url: str | None = None, prepare: DatabasePreparation | None = None,
    clock: Clock | None = None) -> AppContext:
    """Resolve platform infrastructure once and return it to app domain code."""
    definition = get_app(app_name)
    resolved_url = None
    sessions = None
    if metadata is not None or schema is not None:
        if default_database is None or environment_key is None:
            raise ValueError("database apps require a default path and environment key")
        resolved_url = resolve_database_url(database_url, environment_key, default_database)
        sessions = create_session_factory(resolved_url, metadata, prepare, schema=schema)
    return AppContext(definition, resolved_url, sessions, clock)
