import unittest
import asyncio
import json
from pathlib import Path

from tooling.apps import AppDefinitionError, discover_apps, get_app
from tooling.lifecycle import build_app, validate_app, validate_dist


class RepositoryAppTests(unittest.TestCase):
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
                self.assertNotIn('src="', document)
                self.assertNotIn('href="', document)

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
        from apps.chat.database import MessageRepository, create_session_factory
        from apps.chat.server import ConnectionHub

        class SocketDouble:
            def __init__(self) -> None:
                self.events: list[dict[str, object]] = []

            async def accept(self) -> None:
                pass

            async def send_json(self, event: dict[str, object]) -> None:
                self.events.append(event)

            async def send_text(self, payload: str) -> None:
                self.events.append(json.loads(payload))

        database = Path("apps/chat/data/test-chat.db")
        database.unlink(missing_ok=True)
        self.addCleanup(database.unlink, missing_ok=True)
        database_url = f"sqlite:///{database}"
        repository = MessageRepository(create_session_factory(database_url))
        hub, first, second = ConnectionHub(), SocketDouble(), SocketDouble()

        async def exercise_live_room() -> None:
            await hub.connect(first, repository)  # type: ignore[arg-type]
            await hub.connect(second, repository)  # type: ignore[arg-type]
            await hub.publish(repository, "Ada", "Hello, room.")

        asyncio.run(exercise_live_room())
        sent, received = first.events[-1], second.events[-1]
        self.assertEqual(sent, received)
        self.assertEqual(sent["type"], "message")
        self.assertEqual(sent["message"]["author"], "Ada")  # type: ignore[index]
        self.assertEqual(sent["message"]["body"], "Hello, room.")  # type: ignore[index]

        restarted = MessageRepository(create_session_factory(database_url))
        self.assertEqual(restarted.all(), [sent["message"]])


if __name__ == "__main__":
    unittest.main()
