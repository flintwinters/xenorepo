"""Strict reusable SQLAlchemy column templates and metadata conformance."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import TypeEngine
from sqlalchemy.orm import Mapped, mapped_column


@dataclass(frozen=True)
class ColumnContract:
    """The schema properties a shared infrastructure column must preserve."""

    type_: type[TypeEngine[Any]]
    nullable: bool
    primary_key: bool = False
    length: int | None = None
    timezone: bool | None = None


PROVENANCE_COLUMN_CONTRACTS = {
    "client_host": ColumnContract(String, nullable=True, length=255),
    "user_agent": ColumnContract(String, nullable=True, length=500),
    "origin": ColumnContract(String, nullable=True, length=500),
}

REALTIME_CONNECTION_COLUMN_CONTRACTS = {
    "id": ColumnContract(String, nullable=False, primary_key=True, length=36),
    "connected_at": ColumnContract(DateTime, nullable=False, timezone=True),
    "disconnected_at": ColumnContract(DateTime, nullable=True, timezone=True),
    **PROVENANCE_COLUMN_CONTRACTS,
}


class ClientProvenanceColumns:
    """Canonical nullable transport facts for persisted client activity."""

    client_host: Mapped[str | None] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    origin: Mapped[str | None] = mapped_column(String(500))


class RealtimeConnectionTable(ClientProvenanceColumns):
    """Canonical identity, lifecycle, and provenance for realtime connections."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def assert_column_conformance(
    model: Any,
    contracts: dict[str, ColumnContract],
) -> None:
    """Assert that a mapped model preserves every required column contract."""
    table = model.__table__
    for name, contract in contracts.items():
        if name not in table.c:
            raise AssertionError(f"{table.name}.{name} is required")
        _assert_column_conformance(table.c[name], contract)


def assert_realtime_connection_conformance(model: Any) -> None:
    """Assert the strict shared realtime-connection schema contract."""
    assert_column_conformance(model, REALTIME_CONNECTION_COLUMN_CONTRACTS)


def _assert_column_conformance(column: Column[Any], contract: ColumnContract) -> None:
    actual = {
        "type": type(column.type),
        "length": getattr(column.type, "length", None),
        "timezone": getattr(column.type, "timezone", None),
        "nullable": column.nullable,
        "primary_key": column.primary_key,
    }
    expected = {
        "type": contract.type_,
        "length": contract.length,
        "timezone": contract.timezone,
        "nullable": contract.nullable,
        "primary_key": contract.primary_key,
    }
    if actual != expected:
        raise AssertionError(
            f"{column.table.name}.{column.name} violates its shared column contract: "
            f"expected {expected}, got {actual}"
        )
