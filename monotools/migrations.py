"""Orchestrate versioned and recoverable monoapp database migrations.

The migration ledger, backup phase, ordered steps, and transactional recording
make schema evolution repeatable while preserving explicit recovery evidence.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil

from sqlalchemy import Column, DateTime, Engine, Integer, MetaData, String, Table, inspect, select, text
from sqlalchemy.engine import Connection

from monotools.identity import DatabaseSchema


MigrationAction = Callable[[Connection], None]
MIGRATION_METADATA = MetaData()
MIGRATION_RECORDS = Table(
    "monotools_migrations",
    MIGRATION_METADATA,
    Column("version", Integer, primary_key=True),
    Column("name", String(255), nullable=False, unique=True),
    Column("applied_at", DateTime(timezone=True), nullable=False),
)


@dataclass(frozen=True)
class Migration:
    """One ordered domain migration surrounding canonical schema creation."""

    version: int
    name: str
    pre_schema: MigrationAction | None = None
    post_schema: MigrationAction | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("migration versions must be positive")
        if not self.name.strip():
            raise ValueError("migration names must not be empty")


@dataclass(frozen=True)
class MigrationReport:
    applied: tuple[int, ...]
    backup: Path | None


class MigrationError(RuntimeError):
    """Raised when migration ordering or resulting integrity is invalid."""


def run_migrations(engine: Engine, schema: DatabaseSchema,
    migrations: Iterable[Migration], *, data_directory: Path) -> MigrationReport:
    """Apply pending migrations once, with a visible SQLite safety copy."""
    ordered = tuple(sorted(migrations, key=lambda item: item.version))
    _validate_migrations(ordered)
    records_exist = inspect(engine).has_table(MIGRATION_RECORDS.name)
    if records_exist:
        with engine.connect() as connection:
            applied = frozenset(connection.scalars(select(MIGRATION_RECORDS.c.version)))
    else:
        applied = frozenset()
    pending = tuple(migration for migration in ordered if migration.version not in applied)
    if not pending:
        return MigrationReport((), None)

    backup = _backup_sqlite_once(engine, data_directory)
    MIGRATION_METADATA.create_all(engine)
    completed: list[int] = []
    for migration in pending:
        try:
            with engine.begin() as connection:
                if migration.pre_schema is not None:
                    migration.pre_schema(connection)
            schema.metadata.create_all(engine, tables=schema.tables)
            with engine.begin() as connection:
                if migration.post_schema is not None:
                    migration.post_schema(connection)
                _assert_foreign_keys(connection)
                connection.execute(MIGRATION_RECORDS.insert().values(
                    version=migration.version, name=migration.name,
                    applied_at=datetime.now(timezone.utc)))
        except Exception as error:
            raise MigrationError(
                f"migration {migration.version} ({migration.name}) failed; "
                f"restore {backup} before retrying if the domain phase was not idempotent: {error}"
            ) from error
        completed.append(migration.version)
    return MigrationReport(tuple(completed), backup)


def _validate_migrations(migrations: tuple[Migration, ...]) -> None:
    versions = [migration.version for migration in migrations]
    names = [migration.name for migration in migrations]
    if len(versions) != len(set(versions)):
        raise MigrationError("migration versions must be unique")
    if len(names) != len(set(names)):
        raise MigrationError("migration names must be unique")
    if versions and versions != list(range(1, max(versions) + 1)):
        raise MigrationError("migration versions must be contiguous from 1")


def _backup_sqlite_once(engine: Engine, data_directory: Path) -> Path | None:
    if engine.dialect.name != "sqlite" or not engine.url.database:
        return None
    source = Path(engine.url.database)
    if not source.exists() or source.stat().st_size == 0:
        return None
    data_directory.mkdir(parents=True, exist_ok=True)
    backup = data_directory / f"{source.stem}.pre-monotools.sqlite3"
    if not backup.exists():
        shutil.copy2(source, backup)
    return backup


def _assert_foreign_keys(connection: Connection) -> None:
    if connection.dialect.name != "sqlite":
        return
    violations = connection.execute(text("PRAGMA foreign_key_check")).all()
    if violations:
        details = ", ".join(f"{row[0]} row {row[1]}" for row in violations)
        raise MigrationError(f"foreign-key verification failed: {details}")


def migration_versions(engine: Engine) -> tuple[int, ...]:
    """Return installed versions without mutating an uninitialized database."""
    if not inspect(engine).has_table(MIGRATION_RECORDS.name):
        return ()
    with engine.connect() as connection:
        return tuple(connection.scalars(
            select(MIGRATION_RECORDS.c.version).order_by(MIGRATION_RECORDS.c.version)))
