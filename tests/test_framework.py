"""Contracts for central persistence, validation, and realtime primitives."""

from pathlib import Path
from types import SimpleNamespace
import unittest

from sqlalchemy import ForeignKey, Integer, MetaData, Table, Column, text
from sqlalchemy.exc import IntegrityError

from tests.support import SocketDouble, run_async
from tooling.apps import discover_apps
from tooling.database import create_session_factory
from tooling.realtime import (
    ConnectionRegistry,
    bounded_text,
    client_provenance,
    encode_event,
    websocket_origin_allowed,
)


class SharedFrameworkTests(unittest.TestCase):
    database = Path("apps/chat/data/test-framework.db")

    def tearDown(self) -> None:
        self.database.unlink(missing_ok=True)

    def test_declared_capabilities_describe_existing_apps(self) -> None:
        capabilities = {app.name: app.capabilities for app in discover_apps()}
        self.assertEqual(capabilities["calculator"], frozenset())
        self.assertEqual(capabilities["chat"], frozenset({"database", "realtime"}))
        self.assertEqual(capabilities["microblog"], frozenset({"database"}))

    def test_database_factory_enforces_sqlite_foreign_keys(self) -> None:
        metadata = MetaData()
        Table("parents", metadata, Column("id", Integer, primary_key=True))
        children = Table("children", metadata, Column("id", Integer, primary_key=True),
            Column("parent_id", ForeignKey("parents.id")))
        sessions = create_session_factory(f"sqlite:///{self.database}", metadata)
        self.addCleanup(sessions.kw["bind"].dispose)

        with sessions() as session:
            self.assertEqual(session.scalar(text("PRAGMA foreign_keys")), 1)
        with self.assertRaises(IntegrityError), sessions.begin() as session:
            session.execute(children.insert().values(id=1, parent_id=999))

    def test_registry_filters_sends_and_reports_stale_connections(self) -> None:
        registry = ConnectionRegistry[str]()
        first, second, stale = SocketDouble(), SocketDouble(), SocketDouble(fail_sends=True)
        registry.register(first, "room-a")
        registry.register(second, "room-b")
        registry.register(stale, "room-a")

        report = run_async(registry.broadcast({"type": "signal", "value": "✓"},
            lambda room: room == "room-a"))
        self.assertEqual(report.delivered, ("room-a",))
        self.assertEqual([item.context for item in report.disconnected], ["room-a"])
        self.assertEqual(first.events, [{"type": "signal", "value": "✓"}])
        self.assertEqual(second.events, [])
        self.assertEqual(len(registry), 2)
        direct = run_async(registry.send(second, {"type": "private"}))
        self.assertEqual(direct.delivered, ("room-b",))

    def test_realtime_validation_and_provenance_are_strict(self) -> None:
        self.assertEqual(bounded_text("  hello  ", 5), "hello")
        for invalid in (None, 17, "", "abcdef"):
            self.assertIsNone(bounded_text(invalid, 5))
        self.assertEqual(encode_event({"message": "café"}), '{"message":"café"}')

        socket = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            url=SimpleNamespace(scheme="ws"),
            headers={"host": "arena.test", "origin": "http://arena.test",
                "user-agent": "test-suite"},
        )
        self.assertTrue(websocket_origin_allowed(socket))
        self.assertEqual(client_provenance(socket), {"client_host": "127.0.0.1",
            "user_agent": "test-suite", "origin": "http://arena.test"})
        socket.headers["origin"] = "https://foreign.test"
        self.assertFalse(websocket_origin_allowed(socket))


if __name__ == "__main__":
    unittest.main()
