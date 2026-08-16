"""Durable chat storage behind a backend-independent SQLAlchemy boundary."""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author: Mapped[str] = mapped_column(String(40))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def as_dict(self) -> dict[str, int | str]:
        timestamp = self.created_at
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return {
            "id": self.id,
            "author": self.author,
            "body": self.body,
            "created_at": timestamp.isoformat().replace("+00:00", "Z"),
        }


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    options = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=options)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


class MessageRepository:
    """Transaction boundary for the shared chronological message stream."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def all(self) -> list[dict[str, int | str]]:
        with self.sessions() as session:
            messages = session.scalars(select(Message).order_by(Message.id)).all()
            return [message.as_dict() for message in messages]

    def add(self, author: str, body: str) -> dict[str, int | str]:
        with self.sessions.begin() as session:
            message = Message(
                author=author,
                body=body,
                created_at=datetime.now(timezone.utc),
            )
            session.add(message)
            session.flush()
            return message.as_dict()


def sqlite_url(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"
