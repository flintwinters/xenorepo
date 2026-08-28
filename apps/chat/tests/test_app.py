"""Chat-owned product contracts."""

from datetime import datetime, timezone
from pathlib import Path
import unittest

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text
from sqlalchemy import create_engine, func, inspect, select

from apps.chat.backend.database import (
    ChatMessage, ChatRepository, ConnectionSession, MessageDelivery, Participant,
    ParticipantAlias, Room, create_session_factory,
)
from apps.chat.backend.server import ConnectionHub
from monotools.appkit import SystemClock
from monotools.orm import (
    REALTIME_CONNECTION_COLUMN_CONTRACTS,
    assert_realtime_connection_conformance,
)
from tests.support import SocketDouble, run_async


class ChatTests(unittest.TestCase):
    def test_connection_model_conforms_with_chat_relationships(self) -> None:
        assert_realtime_connection_conformance(ConnectionSession)
        extensions = set(ConnectionSession.__table__.c.keys()) - set(
            REALTIME_CONNECTION_COLUMN_CONTRACTS)
        self.assertEqual(extensions, {"room_id", "participant_id"})
        for name in extensions:
            column = ConnectionSession.__table__.c[name]
            self.assertTrue(column.index)
            self.assertEqual(len(column.foreign_keys), 1)

        timestamp = SystemClock().now()
        connection = ConnectionSession(id="chat", room_id=1, participant_id=None,
            connected_at=timestamp, disconnected_at=None, client_host="127.0.0.1",
            user_agent="tests", origin=None)
        self.assertEqual((connection.room_id, connection.connected_at), (1, timestamp))

    def test_messages_are_durable_across_repository_restart(self) -> None:
        database = Path("apps/chat/data/test-owned-chat.db")
        database.unlink(missing_ok=True)
        self.addCleanup(database.unlink, missing_ok=True)
        url = f"sqlite:///{database}"
        first_sessions = create_session_factory(url)
        self.addCleanup(first_sessions.kw["bind"].dispose)
        first = ChatRepository(first_sessions)
        session_id = first.open_session({
            "client_host": "127.0.0.1", "user_agent": "test", "origin": None,
        })
        first.identify(session_id, "0f314f25-e6af-49fe-80be-bfb9505b1071", "Ada")
        message = first.add(session_id, "Ada", "Owned suite.", "owned-1")
        second_sessions = create_session_factory(url)
        self.addCleanup(second_sessions.kw["bind"].dispose)
        self.assertEqual(ChatRepository(second_sessions).all(), [message])

    def test_history_is_persistent_and_broadcast_to_every_connection(self) -> None:
        database = Path("apps/chat/data/test-chat.db")
        database.unlink(missing_ok=True)
        self.addCleanup(database.unlink, missing_ok=True)
        database_url = f"sqlite:///{database}"
        sessions = create_session_factory(database_url)
        self.addCleanup(sessions.kw["bind"].dispose)
        repository = ChatRepository(sessions)
        hub, first, second = ConnectionHub(), SocketDouble(), SocketDouble()
        participant_id = "0f314f25-e6af-49fe-80be-bfb9505b1071"

        async def exercise_live_room() -> None:
            await hub.connect(first, repository)  # type: ignore[arg-type]
            await hub.connect(second, repository)  # type: ignore[arg-type]
            self.assertEqual(first.events[-1], {"type": "presence", "count": 2})
            hub.identify(first, repository, participant_id, "Ada")  # type: ignore[arg-type]
            await hub.publish(first, repository, "Ada", "Hello, room.",
                "c58ee53e-e44e-4db7-a51f-e53544379a93")  # type: ignore[arg-type]

        run_async(exercise_live_room())
        sent, received = first.events[-1], second.events[-1]
        self.assertEqual(sent, received)
        self.assertEqual(sent["message"]["author"], "Ada")  # type: ignore[index]
        self.assertEqual(sent["message"]["body"], "Hello, room.")  # type: ignore[index]
        restarted_sessions = create_session_factory(database_url)
        self.addCleanup(restarted_sessions.kw["bind"].dispose)
        self.assertEqual(ChatRepository(restarted_sessions).all(), [sent["message"]])

        second.fail_sends = True
        run_async(hub.broadcast({"type": "probe"}, repository))
        with sessions() as session:
            counts = {model.__tablename__: session.scalar(select(func.count()).select_from(model))
                for model in (Room, Participant, ParticipantAlias, ConnectionSession,
                    ChatMessage, MessageDelivery)}
            closed = session.scalars(select(ConnectionSession)
                .where(ConnectionSession.disconnected_at.is_not(None))).all()
        self.assertEqual(counts, {"rooms": 1, "participants": 1,
            "participant_aliases": 1, "connection_sessions": 2,
            "chat_messages": 1, "message_deliveries": 2})
        self.assertEqual((len(closed), len(hub.connections)), (1, 1))

    def test_legacy_messages_migrate_without_losing_facts(self) -> None:
        database = Path("apps/chat/data/test-chat-migration.db")
        database.unlink(missing_ok=True)
        self.addCleanup(database.unlink, missing_ok=True)
        database_url = f"sqlite:///{database}"
        engine, metadata = create_engine(database_url), MetaData()
        legacy = Table("messages", metadata,
            Column("id", Integer, primary_key=True), Column("author", String(40)),
            Column("body", Text), Column("created_at", DateTime(timezone=True)))
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(legacy.insert().values(id=7, author="Grace",
                body="Preserve this.", created_at=datetime(2026, 1, 2, 3, 4,
                    tzinfo=timezone.utc)))

        sessions = create_session_factory(database_url)
        self.addCleanup(sessions.kw["bind"].dispose)
        history = ChatRepository(sessions).all()

        self.assertNotIn("messages", inspect(engine).get_table_names())
        self.assertEqual(len(history), 1)
        self.assertEqual((history[0]["id"], history[0]["author"], history[0]["body"]),
            (7, "Grace", "Preserve this."))
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
