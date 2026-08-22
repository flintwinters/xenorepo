"""Normalized, lossless persistence for the anonymous chat domain."""

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from monotools.appkit import SystemClock
from monotools.database import create_session_factory as _create_session_factory
from monotools.orm import RealtimeConnectionTable


class Base(DeclarativeBase):
    pass


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    """Compatibility factory for tests and standalone app-domain consumers."""
    return _create_session_factory(database_url, Base.metadata, _migrate_legacy)


class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ParticipantAlias(Base):
    __tablename__ = "participant_aliases"
    __table_args__ = (UniqueConstraint("participant_id", "display_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(40), index=True)
    first_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConnectionSession(RealtimeConnectionTable, Base):
    __tablename__ = "connection_sessions"
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    participant_id: Mapped[str | None] = mapped_column(ForeignKey("participants.id"), index=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    alias_id: Mapped[int] = mapped_column(ForeignKey("participant_aliases.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("connection_sessions.id"), index=True)
    client_message_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MessageDelivery(Base):
    __tablename__ = "message_deliveries"
    __table_args__ = (UniqueConstraint("message_id", "session_id", "event_type"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("connection_sessions.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _room(session: Session, at: datetime) -> Room:
    room = session.scalar(select(Room).where(Room.slug == "common"))
    if room is None:
        room = Room(slug="common", title="Common Room", created_at=at)
        session.add(room)
        session.flush()
    return room


def _alias(session: Session, participant: Participant, name: str, at: datetime) -> ParticipantAlias:
    alias = session.scalar(select(ParticipantAlias).where(
        ParticipantAlias.participant_id == participant.id,
        ParticipantAlias.display_name == name,
    ))
    if alias is None:
        alias = ParticipantAlias(participant_id=participant.id, display_name=name, first_used_at=at, last_used_at=at)
        session.add(alias)
    else:
        alias.last_used_at = at
    session.flush()
    return alias


def _migrate_legacy(engine: Engine) -> None:
    from sqlalchemy import MetaData, Table

    if "messages" not in inspect(engine).get_table_names():
        return
    legacy = Table("messages", MetaData(), autoload_with=engine)
    with Session(engine) as session, session.begin():
        room = _room(session, datetime.now(timezone.utc))
        for row in session.execute(select(legacy).order_by(legacy.c.id)).mappings():
            at, author = row["created_at"], row["author"]
            participant_id = str(uuid5(NAMESPACE_URL, f"common-room:legacy:{author}"))
            participant = session.get(Participant, participant_id)
            if participant is None:
                participant = Participant(id=participant_id, first_seen_at=at, last_seen_at=at)
                session.add(participant)
            participant.last_seen_at = max(participant.last_seen_at, at)
            alias = _alias(session, participant, author, at)
            connection = ConnectionSession(
                id=str(uuid5(NAMESPACE_URL, f"common-room:legacy-message:{row['id']}")),
                room_id=room.id, participant_id=participant.id, connected_at=at,
                disconnected_at=at, client_host=None, user_agent="legacy-import", origin=None,
            )
            session.add(connection)
            session.flush()
            session.add(ChatMessage(
                id=row["id"], room_id=room.id, participant_id=participant.id,
                alias_id=alias.id, session_id=connection.id, client_message_id=None,
                body=row["body"], created_at=at,
            ))
    legacy.drop(engine)


class ChatRepository:
    def __init__(self, sessions: sessionmaker[Session], clock: Callable[[], datetime] | None = None) -> None:
        self.sessions = sessions
        self.clock = clock or SystemClock().now

    def open_session(self, metadata: dict[str, str | None]) -> str:
        identifier = str(uuid4())
        with self.sessions.begin() as session:
            room = _room(session, self.clock())
            session.add(ConnectionSession(id=identifier, room_id=room.id, participant_id=None,
                connected_at=self.clock(), disconnected_at=None, **metadata))
        return identifier

    def identify(self, session_id: str, participant_id: str, name: str) -> None:
        at = self.clock()
        with self.sessions.begin() as session:
            participant = session.get(Participant, participant_id)
            if participant is None:
                participant = Participant(id=participant_id, first_seen_at=at, last_seen_at=at)
                session.add(participant)
            participant.last_seen_at = at
            _alias(session, participant, name, at)
            session.get(ConnectionSession, session_id).participant_id = participant.id

    def close_session(self, session_id: str) -> None:
        with self.sessions.begin() as session:
            session.get(ConnectionSession, session_id).disconnected_at = self.clock()

    def all(self) -> list[dict[str, int | str]]:
        with self.sessions() as session:
            rows = session.execute(select(ChatMessage, ParticipantAlias.display_name)
                .join(ParticipantAlias).order_by(ChatMessage.id)).all()
            return [self._serialize(message, alias) for message, alias in rows]

    def add(self, session_id: str, name: str, body: str, client_id: str | None) -> dict[str, int | str]:
        at = self.clock()
        with self.sessions.begin() as session:
            connection = session.get(ConnectionSession, session_id)
            participant = session.get(Participant, connection.participant_id)
            alias = _alias(session, participant, name, at)
            message = ChatMessage(room_id=connection.room_id, participant_id=participant.id,
                alias_id=alias.id, session_id=session_id, client_message_id=client_id,
                body=body, created_at=at)
            session.add(message)
            session.flush()
            return self._serialize(message, alias.display_name)

    def delivered(self, message_id: int, session_id: str) -> None:
        with self.sessions.begin() as session:
            session.add(MessageDelivery(message_id=message_id, session_id=session_id,
                    event_type="sent", occurred_at=self.clock()))

    @staticmethod
    def _serialize(message: ChatMessage, author: str) -> dict[str, int | str]:
        timestamp = message.created_at
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return {"id": message.id, "author": author, "body": message.body,
            "created_at": timestamp.isoformat().replace("+00:00", "Z")}
