"""Schema-versioned persistence for explicit repository snapshots."""

from collections.abc import Callable, Mapping
from datetime import datetime
import json

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from monotools.runtime.appkit import SystemClock


SCHEMA_VERSION = 1


class Base(DeclarativeBase):
    pass


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("schema_version", "fingerprint",
        name="snapshot_version_fingerprint"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64))
    revision: Mapped[str] = mapped_column(String(64))
    dirty: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metrics_json: Mapped[str] = mapped_column(Text)


def _view(snapshot: Snapshot) -> dict[str, object]:
    return {
        "id": snapshot.id,
        "schema_version": snapshot.schema_version,
        "fingerprint": snapshot.fingerprint,
        "revision": snapshot.revision,
        "dirty": bool(snapshot.dirty),
        "captured_at": snapshot.captured_at.isoformat(),
        "metrics": json.loads(snapshot.metrics_json),
    }


class SnapshotRepository:
    def __init__(self, sessions: sessionmaker[Session],
        clock: Callable[[], datetime] | None = None) -> None:
        self.sessions = sessions
        self.clock = clock or SystemClock().now

    def list(self) -> list[dict[str, object]]:
        with self.sessions() as session:
            values = session.scalars(select(Snapshot).where(
                Snapshot.schema_version == SCHEMA_VERSION
            ).order_by(Snapshot.captured_at, Snapshot.id)).all()
            return [_view(item) for item in values]

    def latest(self) -> dict[str, object] | None:
        values = self.list()
        return values[-1] if values else None

    def record(self, fingerprint: str, revision: str, dirty: bool,
        metrics: Mapping[str, int]) -> tuple[dict[str, object], bool]:
        encoded = json.dumps(dict(metrics), sort_keys=True, separators=(",", ":"))
        with self.sessions.begin() as session:
            existing = session.scalar(select(Snapshot).where(
                Snapshot.schema_version == SCHEMA_VERSION,
                Snapshot.fingerprint == fingerprint))
            if existing is not None:
                return _view(existing), False
            snapshot = Snapshot(schema_version=SCHEMA_VERSION, fingerprint=fingerprint,
                revision=revision, dirty=int(dirty), captured_at=self.clock(), metrics_json=encoded)
            session.add(snapshot)
            session.flush()
            return _view(snapshot), True
