"""Contracts for central persistence, validation, and realtime primitives."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import DateTime, ForeignKey, Integer, MetaData, String, Table, Column, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from starlette.websockets import WebSocketDisconnect

from tests.support import SocketDouble, run_async
from monotools.auth import issue_opaque_credential, opaque_credential_digest
from monotools.appkit import SystemClock, create_app_context
from monotools.database import create_session_factory, resolve_database_url
from monotools.identity import (
    Account, AccountEmail, AccountHandle, AccountName,
    AuthenticationSession as CanonicalSession, DatabaseSchema, PasswordCredential,
    RealtimeConnection, SCHEMA_GROUPS, add_handle, create_account, issue_session,
    resolve_session, revoke_session, set_password, verify_password,
)
from monotools.migrations import Migration, migration_versions, run_migrations
from monotools.orm import (
    REALTIME_CONNECTION_COLUMN_CONTRACTS,
    RealtimeConnectionTable,
    assert_realtime_connection_conformance,
)
from monotools.realtime import (
    ConnectionRegistry,
    bounded_text,
    client_provenance,
    encode_event,
    websocket_origin_allowed,
)


class FixtureBase(DeclarativeBase):
    pass


class FixtureOwner(FixtureBase):
    __tablename__ = "fixture_owners"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class FixtureConnection(RealtimeConnectionTable, FixtureBase):
    __tablename__ = "fixture_connections"
    owner_id: Mapped[int] = mapped_column(ForeignKey("fixture_owners.id"), index=True)


class SharedFrameworkTests(unittest.TestCase):
    database = Path("tests/data/test-framework.db")

    def tearDown(self) -> None:
        self.database.unlink(missing_ok=True)

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
        definition = SimpleNamespace(name="fixture_app")
        with patch("monotools.appkit.get_app", return_value=definition):
            context = create_app_context("fixture_app", metadata=MetaData(),
                default_database=self.database, environment_key="FIXTURE_DATABASE_URL",
                clock=SystemClock())
        self.assertEqual(context.definition.name, "fixture_app")
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
            headers={"host": "fixture.test", "origin": "http://fixture.test",
                "user-agent": "test-suite"},
        )
        self.assertTrue(websocket_origin_allowed(socket))
        self.assertEqual(client_provenance(socket), {"client_host": "127.0.0.1",
            "user_agent": "test-suite", "origin": "http://fixture.test"})
        socket.headers["origin"] = "https://foreign.test"
        self.assertFalse(websocket_origin_allowed(socket))

    def test_opaque_credentials_have_one_canonical_contract(self) -> None:
        credentials = {issue_opaque_credential() for _ in range(16)}
        self.assertEqual(len(credentials), 16)
        for credential in credentials:
            self.assertRegex(credential, r"^[A-Za-z0-9_-]{43}$")
        expected = "fcd67aa6f012ef6579f191b8a6614d5672d9ff4c725ffce97e06a0e4abc08019"
        self.assertEqual(opaque_credential_digest("opaque-test"), expected)
    def test_realtime_connection_template_has_nullable_client_provenance(self) -> None:
        provenance = {"client_host": "127.0.0.1", "user_agent": "test-suite",
            "origin": "http://fixture.test"}
        expected_lengths = {"client_host": 255, "user_agent": 500, "origin": 500}
        self.assertEqual({name: FixtureConnection.__table__.c[name].type.length
            for name in expected_lengths}, expected_lengths)
        record = FixtureConnection(owner_id=1, **provenance)
        self.assertEqual({name: getattr(record, name) for name in provenance}, provenance)

    def test_realtime_connection_model_conforms_and_retains_extensions(self) -> None:
        assert_realtime_connection_conformance(FixtureConnection)
        self.assertEqual(
            set(FixtureConnection.__table__.c.keys())
            - set(REALTIME_CONNECTION_COLUMN_CONTRACTS),
            {"owner_id"},
        )
        extension = FixtureConnection.__table__.c.owner_id
        self.assertTrue(extension.index)
        self.assertEqual(len(extension.foreign_keys), 1)

        now = SystemClock().now()
        connection = FixtureConnection(id="fixture", owner_id=1,
            connected_at=now, disconnected_at=None, client_host="127.0.0.1",
            user_agent="tests", origin=None)
        self.assertEqual((connection.owner_id, connection.connected_at), (1, now))

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


class CanonicalIdentityFoundationTests(unittest.TestCase):
    database = Path("tests/data/test-identity-foundation.db")
    backup = Path("tests/data/test-identity-foundation.pre-monotools.sqlite3")

    def tearDown(self) -> None:
        self.database.unlink(missing_ok=True)
        self.backup.unlink(missing_ok=True)

    def sessions(self, groups: set[str]):
        factory = create_session_factory(f"sqlite:///{self.database}",
            schema=DatabaseSchema(groups))
        self.addCleanup(factory.kw["bind"].dispose)
        return factory

    def test_schema_rejects_unknown_and_missing_capabilities(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown database schema group"):
            DatabaseSchema({"identity", "imaginary"})
        with self.assertRaisesRegex(ValueError, "missing dependencies: identity"):
            DatabaseSchema({"identity-sessions"})

    def test_each_group_creates_only_its_maximal_table_set(self) -> None:
        expected = {
            "identity": {"accounts"},
            "identity-handles": {"accounts", "account_handles"},
            "identity-names": {"accounts", "account_names"},
            "identity-emails": {"accounts", "account_emails"},
            "identity-passwords": {"accounts", "password_credentials"},
            "identity-sessions": {"accounts", "authentication_sessions"},
            "realtime-records": {"accounts", "realtime_connections"},
        }
        for group, tables in expected.items():
            with self.subTest(group=group):
                self.database.unlink(missing_ok=True)
                groups = {group} | SCHEMA_GROUPS[group].dependencies
                sessions = self.sessions(groups)
                self.assertEqual(set(inspect(sessions.kw["bind"]).get_table_names()), tables)
                sessions.kw["bind"].dispose()

    def test_model_contracts_are_explicit_and_portable(self) -> None:
        timestamp_columns = {
            Account: {"created_at", "updated_at", "last_seen_at", "disabled_at"},
            AccountHandle: {"created_at", "retired_at"},
            AccountName: {"first_used_at", "last_used_at", "retired_at"},
            AccountEmail: {"created_at", "verified_at", "retired_at"},
            PasswordCredential: {"created_at", "retired_at"},
            CanonicalSession: {"issued_at", "expires_at", "last_seen_at", "revoked_at"},
            RealtimeConnection: {"connected_at", "last_seen_at", "disconnected_at"},
        }
        for model, names in timestamp_columns.items():
            with self.subTest(model=model.__name__):
                for name in names:
                    self.assertTrue(model.__table__.c[name].type.timezone)
        self.assertTrue(AccountHandle.__table__.c.canonical_handle.unique)
        self.assertTrue(AccountEmail.__table__.c.normalized_address.unique)
        self.assertTrue(CanonicalSession.__table__.c.credential_digest.unique)
        self.assertTrue(CanonicalSession.__table__.c.expires_at.nullable)
        self.assertTrue(RealtimeConnection.__table__.c.account_id.nullable)

    def test_operations_preserve_history_and_never_store_raw_secrets(self) -> None:
        sessions = self.sessions({"identity", "identity-handles",
            "identity-passwords", "identity-sessions"})
        now = datetime(2026, 8, 23, 12, tzinfo=timezone.utc)
        with sessions.begin() as session:
            account = create_account(session, now, account_id="account-1")
            first = add_handle(session, account.id, "first", now)
            secured = set_password(session, account.id, "correct horse battery staple", now)
            self.assertTrue(verify_password("correct horse battery staple", secured))
            expiring, raw = issue_session(session, account.id, now,
                lifetime=timedelta(hours=1), provenance={"client_host": "127.0.0.1"})
        with sessions.begin() as session:
            second = add_handle(session, "account-1", "second", now + timedelta(seconds=1))
            self.assertIsNotNone(session.get(AccountHandle, first.id).retired_at)
            self.assertIsNone(second.retired_at)
            self.assertEqual(resolve_session(session, raw, now + timedelta(minutes=1)).id,
                expiring.id)
            self.assertTrue(revoke_session(session, raw, now + timedelta(minutes=2)))
            self.assertIsNone(resolve_session(session, raw, now + timedelta(minutes=3)))
            persistent, persistent_raw = issue_session(session, "account-1", now,
                lifetime=None)
        with sessions() as session:
            self.assertIsNotNone(resolve_session(
                session, persistent_raw, now + timedelta(days=999)))
            stored = session.get(CanonicalSession, persistent.id)
            self.assertNotEqual(stored.credential_digest, persistent_raw)
            self.assertNotIn(persistent_raw.encode(), self.database.read_bytes())

    def test_migrations_backup_phase_order_and_idempotence(self) -> None:
        metadata = MetaData()
        legacy = Table("legacy", metadata, Column("id", Integer, primary_key=True))
        sessions = create_session_factory(f"sqlite:///{self.database}", metadata)
        self.addCleanup(sessions.kw["bind"].dispose)
        with sessions.begin() as session:
            session.execute(legacy.insert().values(id=1))
        phases = []
        migration = Migration(1, "identity-foundation",
            pre_schema=lambda connection: phases.append(
                ("pre", inspect(connection).has_table("accounts"))),
            post_schema=lambda connection: phases.append(
                ("post", inspect(connection).has_table("accounts"))))
        schema = DatabaseSchema({"identity"})
        report = run_migrations(sessions.kw["bind"], schema, (migration,),
            data_directory=self.database.parent)
        self.assertEqual(phases, [("pre", False), ("post", True)])
        self.assertEqual(report.applied, (1,))
        self.assertEqual(report.backup, self.backup)
        self.assertTrue(self.backup.is_file())
        self.assertEqual(migration_versions(sessions.kw["bind"]), (1,))
        second = run_migrations(sessions.kw["bind"], schema, (migration,),
            data_directory=self.database.parent)
        self.assertEqual(second.applied, ())
        self.assertIsNone(second.backup)
        self.assertEqual(phases, [("pre", False), ("post", True)])


if __name__ == "__main__":
    unittest.main()
