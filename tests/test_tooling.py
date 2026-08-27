import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from monotools.apps import AppDefinition, AppDefinitionError, FrontendArtifact, ROOT, discover_apps, get_app, load_app
from monotools.cli import app
from monotools.frontend import CONSOLE_SHELL, DocumentParts, compose_console
from monotools.lifecycle import LifecycleError, build_app, validate_app, validate_dist
from monotools.watch import frontend_inputs, watch_frontend
from tests.support import SocketDouble, run_async


class RepositoryAppTests(unittest.TestCase):
    def test_library_catalog_describes_the_shared_frontend_and_backend_boundaries(self) -> None:
        catalog = (ROOT / "LIBRARIES.md").read_text(encoding="utf-8")

        self.assertIn("# Custom Library Catalog", catalog)
        self.assertIn("`monotools/`", catalog)
        self.assertIn("`packages/lit-ui/`", catalog)
        self.assertIn("Applications are consumers; they do not", catalog)
        self.assertIn("import one another.", catalog)

    def test_serve_without_an_app_lists_discovered_choices(self) -> None:
        result = CliRunner().invoke(app, ["serve"])

        self.assertEqual(result.exit_code, 2)
        self.assertIn("choose an application:", result.output)
        for definition in discover_apps():
            self.assertIn(definition.name, result.output)
        first_app = discover_apps()[0]
        self.assertIn(f"Example: manage.py serve {first_app.name}", result.output)

    def test_worminal_user_option_is_discoverable_from_the_managed_serve_command(self) -> None:
        result = CliRunner().invoke(app, ["serve", "--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("--user", result.output)
        self.assertIn("Unix user for Worminal terminal", result.output)

    def test_frontend_watch_is_discoverable_from_the_managed_serve_command(self) -> None:
        result = CliRunner().invoke(app, ["serve", "--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("--watch", result.output)
        self.assertIn("Rebuild frontend artifacts", result.output)

    def test_frontend_watch_rebuilds_declared_and_shared_lit_inputs(self) -> None:
        definition = get_app("worminal")
        inputs = frontend_inputs(definition, ROOT)

        self.assertIn(definition.directory / "frontend" / "index.ts", inputs)
        self.assertIn(definition.directory / "frontend" / "services" / "api.ts", inputs)
        self.assertIn(ROOT / "packages" / "lit-ui" / "src" / "index.ts", inputs)
        self.assertIn(ROOT / "packages" / "lit-ui" / "src" / "styles.ts", inputs)
        self.assertIn(ROOT / "tsconfig.frontend.json", inputs)
        report = Mock()
        with patch("monotools.watch._snapshot", side_effect=[
                ((Path("source"), 1),), ((Path("source"), 2),)
            ]), patch("monotools.watch.build_app") as rebuild, patch(
                "monotools.watch.time.sleep", side_effect=[None, RuntimeError("stop")]
            ):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                watch_frontend(definition, ROOT, report, interval=0)
        rebuild.assert_called_once_with(definition, ROOT)
        report.assert_called_once_with("Rebuilt worminal frontend")

    def test_status_reports_the_organization_of_every_discovered_app(self) -> None:
        result = CliRunner().invoke(app, ["status"])

        self.assertEqual(result.exit_code, 0)
        definitions = discover_apps()
        for name in (definition.name for definition in definitions):
            with self.subTest(app=name):
                self.assertIn(name, result.output)
        self.assertIn("README", result.output)
        self.assertIn("Source", result.output)
        self.assertIn(f"{len(definitions)} managed app(s)", result.output)
        self.assertIn("manage.py check", result.output)

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

    def test_yaml_metadata_rejects_invalid_declarations_with_actionable_errors(self) -> None:
        base = """name: fixture
title: Fixture
module: apps.fixture.backend.server
frontend:
  artifacts:
    index:
      format: document
      source: frontend/index.html
      output: index.html
      shell: console
  routes:
    /: index
"""
        cases = {
            "malformed": ("name: [\n", "malformed YAML"),
            "duplicate": (base.replace("title: Fixture\n", "title: Fixture\ntitle: Again\n"), "duplicate key"),
            "unknown-artifact": (base.replace("/: index", "/: missing"), "unknown frontend artifact"),
            "reserved-route": (base.replace("/: index", "/health: index"), "reserved by the platform"),
            "invalid-output": (base.replace("output: index.html", "output: ../index.html"), "normalized relative path"),
        }
        with TemporaryDirectory(dir=ROOT / "tests", prefix="metadata-") as temporary:
            directory = Path(temporary) / "fixture"
            directory.mkdir()
            (directory / "frontend").mkdir()
            (directory / "backend").mkdir()
            (directory / "manage.py").touch()
            for name, (contents, message) in cases.items():
                with self.subTest(case=name):
                    (directory / "app.yaml").write_text(contents, encoding="utf-8")
                    with self.assertRaisesRegex(AppDefinitionError, message):
                        load_app(directory)

    def test_yaml_metadata_enforces_monoapp_implementation_boundaries(self) -> None:
        metadata = """name: fixture
title: Fixture
module: apps.fixture.backend.server
frontend:
  artifacts:
    index:
      format: document
      source: frontend/index.html
      output: index.html
      shell: console
  routes:
    /: index
"""
        cases = {
            "missing frontend": ("frontend", "missing required directories: frontend"),
            "missing backend": ("backend", "missing required directories: backend"),
            "missing manager": ("manage.py", "root Python files must be exactly manage.py"),
            "root implementation": ("server.py", "found: manage.py, server.py"),
            "wrong module": ("module", "module must be 'apps.fixture.backend.server'"),
            "misplaced source": ("source", "frontend sources must be beneath frontend/"),
        }
        with TemporaryDirectory(dir=ROOT / "tests", prefix="structure-") as temporary:
            for index, (case, (mutation, message)) in enumerate(cases.items()):
                with self.subTest(case=case):
                    directory = Path(temporary) / f"case-{index}" / "fixture"
                    (directory / "frontend").mkdir(parents=True)
                    (directory / "backend").mkdir()
                    (directory / "manage.py").touch()
                    contents = metadata
                    if mutation in {"frontend", "backend", "manage.py"}:
                        target = directory / mutation
                        target.rmdir() if target.is_dir() else target.unlink()
                    elif mutation == "server.py":
                        (directory / mutation).touch()
                    elif mutation == "module":
                        contents = contents.replace(
                            "apps.fixture.backend.server", "apps.fixture.server")
                    else:
                        contents = contents.replace(
                            "source: frontend/index.html", "source: index.html")
                    (directory / "app.yaml").write_text(contents, encoding="utf-8")
                    with self.assertRaisesRegex(AppDefinitionError, message):
                        load_app(directory)

    def test_runtime_registers_one_independent_document_endpoint_per_metadata_route(self) -> None:
        definition = AppDefinition(
            name="fixture",
            title="Fixture pages",
            directory=ROOT / "tests",
            module="tests.fixture",
            artifacts=(
                FrontendArtifact("home", "document", Path("home.html"), Path("home.html"), "console"),
                FrontendArtifact("about", "document", Path("about.html"), Path("about.html"), "console"),
            ),
            routes=(("/", "home"), ("/about", "about")),
            capabilities=frozenset(),
        )
        from monotools.runtime import create_application

        with patch("monotools.runtime.get_app", return_value=definition):
            application = create_application("fixture")
        routes = {route.path: route for route in application.routes if hasattr(route, "path")}
        self.assertEqual(routes["/"].endpoint(), ROOT / "tests" / "dist" / "home.html")
        self.assertEqual(routes["/about"].endpoint(), ROOT / "tests" / "dist" / "about.html")
        self.assertEqual(routes["/health"].endpoint(), {"status": "ok"})

    def test_every_discovered_app_validates_and_builds(self) -> None:
        for definition in discover_apps():
            with self.subTest(app=definition.name):
                validate_app(definition, ROOT)
                build_app(definition, ROOT)
                validate_dist(definition)

    def test_document_frontends_build_as_self_contained_documents(self) -> None:
        definitions = (
            definition
            for definition in discover_apps()
            if definition.frontend_format == "document"
        )
        for definition in definitions:
            with self.subTest(app=definition.name):
                build_app(definition, ROOT)
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
                self.assertEqual(document.count("<script>"), 1)
                self.assertIn('<meta name="monotools-shell" content="console">', document)
                self.assertIn("/* monotools.frontend: console shell */", document)
                self.assertNotIn('src="', document)
                self.assertNotIn('href="', document)

    def test_console_composition_preserves_app_owned_parts(self) -> None:
        document = compose_console(DocumentParts(
            title="Control & Monitor",
            body='<main id="app">READY</main>',
            styles="#app { color: var(--aqua); }",
            script='document.title = "READY";',
        ))

        self.assertIn("/* monotools.frontend: console shell */", document)
        self.assertIn("--yellow: #fabd2f", CONSOLE_SHELL)
        self.assertIn("--chrome-rim: #b7cfca", CONSOLE_SHELL)
        self.assertIn(".pane-title.green, .title.green", CONSOLE_SHELL)
        self.assertIn("--chrome-rim: #d5d87a", CONSOLE_SHELL)
        self.assertIn("--chrome-shade: #57580e", CONSOLE_SHELL)
        self.assertIn("--chrome-rim: #ffaf66", CONSOLE_SHELL)
        self.assertIn("--chrome-shade: #7a3307", CONSOLE_SHELL)
        self.assertIn("--chrome-rim: #edb8c5", CONSOLE_SHELL)
        self.assertIn("--chrome-shade: #65364c", CONSOLE_SHELL)
        self.assertIn("<title>Control &amp; Monitor</title>", document)
        self.assertIn('<main id="app">READY</main>', document)
        self.assertIn("#app { color: var(--aqua); }", document)
        self.assertIn('document.title = "READY";', document)

    def test_document_metadata_declares_the_shared_console_shell(self) -> None:
        for definition in discover_apps():
            with self.subTest(app=definition.name):
                if definition.frontend_format == "document":
                    self.assertEqual(definition.frontend_shell, "console")

    def test_worminal_lit_entry_is_a_composition_boundary(self) -> None:
        definition = get_app("worminal")
        validate_app(definition, ROOT)
        self.assertEqual(definition.routes, (("/worminal", "index"),))
        build_app(definition, ROOT)
        frontend = definition.directory / "frontend"
        source = frontend.joinpath("index.ts").read_text(encoding="utf-8")
        document = definition.dist_directory.joinpath("index.html").read_text(encoding="utf-8")

        self.assertLess(len(source.splitlines()), 20)
        self.assertNotIn("LitElement", source)
        for module in ("desktop.ts", "sessions.ts", "shortcuts.ts", "styles.ts", "types.ts", "services/api.ts"):
            self.assertIn(frontend / module, frontend_inputs(definition, ROOT))
        self.assertIn("+ NEW SHELL", document)
        self.assertIn("LOCALHOST WORKSPACE", document)
        self.assertIn('<meta name="monotools-shell" content="console">', document)
        self.assertNotIn('<script src=', document)
        self.assertNotIn('<link rel="stylesheet"', document)

    def test_lit_type_error_is_actionable_before_build_mutation(self) -> None:
        definition = get_app("worminal")
        output = definition.dist_directory / "index.html"
        before = output.read_bytes()
        failed = Mock(returncode=1, stdout="apps/worminal/frontend/nested/broken.ts:3:7 - error TS2322")

        with patch("monotools.lifecycle.subprocess.run", return_value=failed):
            with self.assertRaisesRegex(LifecycleError, "nested/broken.ts.*TS2322"):
                validate_app(definition, ROOT)
        self.assertEqual(output.read_bytes(), before)

    def test_quiz_has_a_non_diagnostic_psychometric_inventory(self) -> None:
        definition = get_app("quiz")
        build_app(definition, ROOT)
        source = (definition.directory / definition.artifact("index").source).read_text(
            encoding="utf-8"
        )
        document = definition.dist_directory.joinpath("index.html").read_text(encoding="utf-8")

        self.assertEqual(source.count("dimension:"), 8)
        self.assertIn("There are no right answers.", source)
        self.assertIn("NOT A CLINICAL ASSESSMENT", source)
        self.assertIn("profile recorded", source.lower())
        self.assertIn('<div class="pane-body"><ol class="review-list"', source)
        self.assertIn('meta name="monotools-shell" content="console"', document)

    def test_console_data_views_have_a_bounded_scroll_container(self) -> None:
        shell = (ROOT / "monotools" / "frontend.py").read_text(encoding="utf-8")
        components = (ROOT / "packages" / "lit-ui" / "src" / "index.ts").read_text(
            encoding="utf-8"
        )

        self.assertIn(".pane-body { min-height: 0; overflow: auto; }", shell)
        self.assertIn(":host { display: block; min-height: 0; overflow: auto; } table", components)

    def test_console_command_buttons_reverse_their_shadow_when_pressed(self) -> None:
        shell = (ROOT / "monotools" / "frontend.py").read_text(encoding="utf-8")
        components = (ROOT / "packages" / "lit-ui" / "src" / "index.ts").read_text(
            encoding="utf-8"
        )

        self.assertIn("transform: translateY(1px)", shell)
        self.assertIn("linear-gradient(#45413f, #302d2b)", shell)
        self.assertIn("linear-gradient(#242220, #181716)", shell)
        self.assertIn("inset 0 3px 3px #0e0f0f, inset 0 -1px #504945", shell)
        pressed_rule = 'button:active:not(:disabled), button[aria-pressed="true"]:not(:disabled)'
        self.assertIn(pressed_rule, components)
        self.assertIn("linear-gradient(#4a4643, #35312f)", components)
        self.assertIn("var(--console-button-border, #c6b58f)", components)
        self.assertIn("var(--console-button-border-hover, #f0dfb8)", components)
        self.assertIn("transform: translateY(1px)", components)
        self.assertIn("linear-gradient(#242220, #181716)", components)
        self.assertIn("inset 0 3px 4px rgb(0 0 0 / 0.65)", components)
        self.assertIn("inset 0 -1px rgb(255 255 255 / 0.08)", components)
        self.assertNotIn("transition:", components)

    def test_chat_persists_history_and_broadcasts_to_every_connection(self) -> None:
        from apps.chat.backend.database import (
            ChatMessage,
            ChatRepository,
            ConnectionSession,
            MessageDelivery,
            Participant,
            ParticipantAlias,
            Room,
            create_session_factory,
        )
        from apps.chat.backend.server import ConnectionHub
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

        from apps.chat.backend.database import ChatRepository, create_session_factory

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
