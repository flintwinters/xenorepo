import unittest
from pathlib import Path

from typer.testing import CliRunner

from tooling.apps import AppDefinitionError, discover_apps, get_app
from tooling.cli import app
from tooling.frontend import CONSOLE_SHELL, DocumentParts, compose_console
from tooling.lifecycle import build_app, validate_app, validate_dist
from tests.support import SocketDouble, run_async


class RepositoryAppTests(unittest.TestCase):
    def test_serve_without_an_app_lists_discovered_choices(self) -> None:
        result = CliRunner().invoke(app, ["serve"])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("choose an application: calculator, chat, microblog, rps", result.output)
        self.assertIn("Example: manage.py serve calculator", result.output)

    def test_app_catalog_is_nonempty_and_has_unique_names(self) -> None:
        apps = discover_apps()
        names = [app.name for app in apps]

        self.assertTrue(apps, "the repository must contain at least one managed app")
        self.assertEqual(len(names), len(set(names)), "managed app names must be unique")
        for definition in apps:
            with self.subTest(app=definition.name):
                self.assertEqual(definition.directory.name, definition.name)

    def test_unknown_app_error_reports_discovered_catalog(self) -> None:
        available = ", ".join(app.name for app in discover_apps()) or "none"
        with self.assertRaises(AppDefinitionError) as raised:
            get_app("missing")
        self.assertEqual(
            str(raised.exception),
            f"unknown app 'missing'; available: {available}",
        )

    def test_every_discovered_app_validates_and_builds(self) -> None:
        for definition in discover_apps():
            with self.subTest(app=definition.name):
                validate_app(definition)
                build_app(definition)
                validate_dist(definition)

    def test_document_frontends_build_as_self_contained_documents(self) -> None:
        definitions = (
            definition
            for definition in discover_apps()
            if definition.frontend_format == "document"
        )
        for definition in definitions:
            with self.subTest(app=definition.name):
                build_app(definition)
                assets = sorted(
                    path.name
                    for path in definition.dist_directory.iterdir()
                    if path.is_file()
                )
                self.assertEqual(assets, ["index.html"])
                document = (definition.dist_directory / "index.html").read_text(
                    encoding="utf-8"
                )
                self.assertIn("<style>", document)
                self.assertIn("<script>", document)
                self.assertIn('<meta name="tooling-shell" content="console">', document)
                self.assertIn("/* tooling.frontend: console shell */", document)
                self.assertNotIn('src="', document)
                self.assertNotIn('href="', document)

    def test_console_composition_preserves_app_owned_parts(self) -> None:
        document = compose_console(DocumentParts(
            title="Control & Monitor",
            body='<main id="app">READY</main>',
            styles="#app { color: var(--aqua); }",
            script='document.title = "READY";',
        ))

        self.assertIn("/* tooling.frontend: console shell */", document)
        self.assertIn("--yellow: #fabd2f", CONSOLE_SHELL)
        self.assertIn("<title>Control &amp; Monitor</title>", document)
        self.assertIn('<main id="app">READY</main>', document)
        self.assertIn("#app { color: var(--aqua); }", document)
        self.assertIn('document.title = "READY";', document)

    def test_document_metadata_declares_the_shared_console_shell(self) -> None:
        for definition in discover_apps():
            with self.subTest(app=definition.name):
                if definition.frontend_format == "document":
                    self.assertEqual(definition.frontend_shell, "console")

    def test_calculator_preserves_visible_work_across_reload(self) -> None:
        build_app(get_app("calculator"))
        document = get_app("calculator").dist_directory.joinpath("index.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('storageKey="calc98-state-v1"', document)
        self.assertIn("localStorage.setItem(storageKey", document)
        self.assertIn("localStorage.getItem(storageKey)", document)
        self.assertIn("ledger.unshift", document)

    def test_chat_persists_history_and_broadcasts_to_every_connection(self) -> None:
        from apps.chat.database import (
            ChatMessage,
            ChatRepository,
            ConnectionSession,
            MessageDelivery,
            Participant,
            ParticipantAlias,
            Room,
            create_session_factory,
        )
        from apps.chat.server import ConnectionHub
        from sqlalchemy import func, select

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
        self.assertEqual(sent["type"], "message")
        self.assertEqual(sent["message"]["author"], "Ada")  # type: ignore[index]
        self.assertEqual(sent["message"]["body"], "Hello, room.")  # type: ignore[index]

        restarted_sessions = create_session_factory(database_url)
        self.addCleanup(restarted_sessions.kw["bind"].dispose)
        restarted = ChatRepository(restarted_sessions)
        self.assertEqual(restarted.all(), [sent["message"]])
        second.fail_sends = True
        run_async(hub.broadcast({"type": "probe"}, repository))
        with sessions() as session:
            counts = {
                model.__tablename__: session.scalar(select(func.count()).select_from(model))
                for model in (Room, Participant, ParticipantAlias, ConnectionSession,
                    ChatMessage, MessageDelivery)
            }
        self.assertEqual(counts, {"rooms": 1, "participants": 1,
            "participant_aliases": 1, "connection_sessions": 2,
            "chat_messages": 1, "message_deliveries": 2})
        with sessions() as session:
            closed_sessions = session.scalars(select(ConnectionSession)
                .where(ConnectionSession.disconnected_at.is_not(None))).all()
        self.assertEqual(len(closed_sessions), 1)
        self.assertEqual(len(hub.connections), 1)

    def test_chat_migrates_legacy_messages_without_losing_facts(self) -> None:
        from datetime import datetime, timezone

        from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text
        from sqlalchemy import create_engine, inspect

        from apps.chat.database import ChatRepository, create_session_factory

        database = Path("apps/chat/data/test-chat-migration.db")
        database.unlink(missing_ok=True)
        self.addCleanup(database.unlink, missing_ok=True)
        database_url = f"sqlite:///{database}"
        engine, metadata = create_engine(database_url), MetaData()
        legacy = Table("messages", metadata,
            Column("id", Integer, primary_key=True), Column("author", String(40)),
            Column("body", Text), Column("created_at", DateTime(timezone=True)))
        metadata.create_all(engine)
        created_at = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
        with engine.begin() as connection:
            connection.execute(legacy.insert().values(id=7, author="Grace",
                body="Preserve this.", created_at=created_at))

        sessions = create_session_factory(database_url)
        self.addCleanup(sessions.kw["bind"].dispose)
        repository = ChatRepository(sessions)

        self.assertNotIn("messages", inspect(engine).get_table_names())
        history = repository.all()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], 7)
        self.assertEqual(history[0]["author"], "Grace")
        self.assertEqual(history[0]["body"], "Preserve this.")
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
