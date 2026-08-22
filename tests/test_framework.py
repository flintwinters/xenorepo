"""Contracts for central persistence, validation, and realtime primitives."""

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import DateTime, ForeignKey, Integer, MetaData, String, Table, Column, text
from sqlalchemy.exc import IntegrityError
from starlette.websockets import WebSocketDisconnect

from tests.support import SocketDouble, run_async
from apps.chat.database import ConnectionSession as ChatConnectionSession
from apps.microblog.auth import issue_token, token_digest
from apps.microblog.database import AuthenticationSession
from apps.rps.auth import credential_digest, issue_credential
from apps.rps.database import ConnectionSession as RpsConnectionSession
from monotools.auth import issue_opaque_credential, opaque_credential_digest
from monotools.appkit import SystemClock, create_app_context
from monotools.apps import discover_apps
from monotools.database import create_session_factory, resolve_database_url
from monotools.orm import (
    REALTIME_CONNECTION_COLUMN_CONTRACTS,
    assert_realtime_connection_conformance,
)
from monotools.realtime import (
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
        self.assertEqual(capabilities["mailing_list"], frozenset({"database"}))
        self.assertEqual(capabilities["quiz"], frozenset())
        self.assertEqual(capabilities["rps"], frozenset({"database", "realtime"}))
        self.assertEqual(capabilities["worminal"], frozenset({"database", "realtime"}))

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

    def test_database_url_resolution_has_a_stable_override_order(self) -> None:
        default_path = Path("tests/resolved-database.db")
        with patch.dict("os.environ", {"FIXTURE_DATABASE_URL": "postgresql://environment"}):
            self.assertEqual(
                resolve_database_url("sqlite:///explicit.db", "FIXTURE_DATABASE_URL", default_path),
                "sqlite:///explicit.db",
            )
            self.assertEqual(
                resolve_database_url(None, "FIXTURE_DATABASE_URL", default_path),
                "postgresql://environment",
            )
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                resolve_database_url(None, "FIXTURE_DATABASE_URL", default_path),
                "sqlite:///tests/resolved-database.db",
            )

    def test_app_context_centralizes_metadata_database_and_clock(self) -> None:
        context = create_app_context("chat", metadata=MetaData(),
            default_database=self.database, environment_key="CHAT_TEST_DATABASE_URL",
            clock=SystemClock())
        self.assertEqual(context.definition.name, "chat")
        self.assertTrue(context.database_url.startswith("sqlite:///"))
        self.assertIsNotNone(context.sessions)
        self.assertIsNotNone(context.clock.now())

    def test_registry_filters_sends_and_reports_stale_connections(self) -> None:
        registry = ConnectionRegistry[str]()
        first, second = SocketDouble(), SocketDouble()
        stale = SocketDouble(send_error=WebSocketDisconnect(code=1006))
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

    def test_opaque_credentials_have_one_canonical_compatible_contract(self) -> None:
        credentials = {issue_opaque_credential() for _ in range(16)}
        self.assertEqual(len(credentials), 16)
        for credential in credentials:
            self.assertRegex(credential, r"^[A-Za-z0-9_-]{43}$")
        expected = "fcd67aa6f012ef6579f191b8a6614d5672d9ff4c725ffce97e06a0e4abc08019"
        self.assertEqual(opaque_credential_digest("opaque-test"), expected)
        self.assertRegex(issue_token(), r"^[A-Za-z0-9_-]{43}$")
        self.assertRegex(issue_credential(), r"^[A-Za-z0-9_-]{43}$")
        self.assertEqual(token_digest("opaque-test"), expected)
        self.assertEqual(credential_digest("opaque-test"), expected)

    def test_session_models_share_nullable_client_provenance(self) -> None:
        provenance = {"client_host": "127.0.0.1", "user_agent": "test-suite",
            "origin": "http://arena.test"}
        expected_lengths = {"client_host": 255, "user_agent": 500, "origin": 500}
        for model in (ChatConnectionSession, AuthenticationSession, RpsConnectionSession):
            with self.subTest(model=model.__name__):
                self.assertEqual({name: model.__table__.c[name].type.length
                    for name in expected_lengths}, expected_lengths)
                record = model(**provenance)
                self.assertEqual({name: getattr(record, name) for name in provenance}, provenance)

    def test_realtime_connection_models_conform_and_retain_domain_extensions(self) -> None:
        expected_extensions = {
            ChatConnectionSession: {"room_id", "participant_id"},
            RpsConnectionSession: {"player_id"},
        }
        for model, extensions in expected_extensions.items():
            with self.subTest(model=model.__name__):
                assert_realtime_connection_conformance(model)
                self.assertEqual(
                    set(model.__table__.c.keys()) - set(REALTIME_CONNECTION_COLUMN_CONTRACTS),
                    extensions,
                )
                for name in extensions:
                    column = model.__table__.c[name]
                    self.assertTrue(column.index)
                    self.assertEqual(len(column.foreign_keys), 1)

        now = SystemClock().now()
        chat = ChatConnectionSession(id="chat", room_id=1, participant_id=None,
            connected_at=now, disconnected_at=None, client_host="127.0.0.1",
            user_agent="tests", origin=None)
        rps = RpsConnectionSession(id="rps", player_id="player", connected_at=now,
            disconnected_at=now, client_host=None, user_agent="tests", origin="test")
        self.assertEqual((chat.room_id, chat.connected_at), (1, now))
        self.assertEqual((rps.player_id, rps.disconnected_at), ("player", now))

    def test_realtime_connection_conformance_rejects_an_incompatible_model(self) -> None:
        class IncompatibleConnection:
            __table__ = Table(
                "incompatible_connections", MetaData(),
                Column("id", String(32), primary_key=True),
                Column("connected_at", DateTime(timezone=False), nullable=False),
                Column("disconnected_at", DateTime(timezone=True)),
                Column("client_host", String(255)),
                Column("user_agent", String(500)),
                Column("origin", String(500)),
            )

        with self.assertRaisesRegex(AssertionError, "incompatible_connections.id"):
            assert_realtime_connection_conformance(IncompatibleConnection)


if __name__ == "__main__":
    unittest.main()
