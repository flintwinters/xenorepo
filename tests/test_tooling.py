import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from monotools.apps import AppDefinition, AppDefinitionError, FrontendArtifact, ROOT, get_app, load_app
from monotools.frontend import CONSOLE_SHELL, DocumentParts, compose_console
from monotools.lifecycle import (
    LifecycleError,
    build_app,
    validate_dist,
    validate_source_lines,
)
from monotools.watch import frontend_inputs, watch_frontend


class RepositoryAppTests(unittest.TestCase):
    def fixture_definition(self, directory: Path, *, name: str = "sample-lab",
        format_name: str = "document") -> AppDefinition:
        return AppDefinition(
            name=name,
            title="Sample Laboratory",
            directory=directory,
            module=f"apps.{name}.backend.server",
            artifacts=(FrontendArtifact("index", format_name, Path("frontend/index.html"),
                Path("index.html"), "console"),),
            routes=(("/", "index"),),
            capabilities=frozenset(),
        )

    def test_source_line_validation_covers_python_and_typescript(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="source-lines-") as temporary:
            workspace = Path(temporary)
            source = workspace / "apps" / "fixture"
            source.mkdir(parents=True)
            python = source / "example.py"
            typescript = source / "example.ts"
            python.write_text("answer = 42\n", encoding="utf-8")
            typescript.write_text("export const answer = 42;\n", encoding="utf-8")

            validate_source_lines(workspace)
            python.write_text(f'value = "{"p" * 121}"\n', encoding="utf-8")
            typescript.write_text(f'const value = "{"t" * 121}";\n', encoding="utf-8")

            with self.assertRaisesRegex(
                LifecycleError,
                r"apps/fixture/example\.py:1: 131 characters \(maximum 120\)[\s\S]*"
                r"apps/fixture/example\.ts:1: 138 characters \(maximum 120\)",
            ):
                validate_source_lines(workspace)

    def test_library_catalog_describes_the_shared_frontend_and_backend_boundaries(self) -> None:
        catalog = (ROOT / "LIBRARIES.md").read_text(encoding="utf-8")

        self.assertIn("# Custom Library Catalog", catalog)
        self.assertIn("`monotools/`", catalog)
        self.assertIn("`packages/lit-ui/`", catalog)
        self.assertIn("Applications are consumers; they do not", catalog)
        self.assertIn("import one another.", catalog)

    def test_frontend_watch_rebuilds_declared_and_shared_lit_inputs(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="watch-") as temporary:
            directory = Path(temporary) / "sample-lab"
            frontend = directory / "frontend"
            frontend.mkdir(parents=True)
            (frontend / "index.html").touch()
            (frontend / "feature.ts").touch()
            definition = self.fixture_definition(directory, format_name="lit")
            inputs = frontend_inputs(definition, ROOT)

            self.assertIn(frontend / "index.html", inputs)
            self.assertIn(frontend / "feature.ts", inputs)
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
            report.assert_called_once_with("Rebuilt sample-lab frontend")

    def test_unknown_app_error_reports_discovered_catalog(self) -> None:
        definitions = (self.fixture_definition(ROOT / "tests", name="alpha-lab"),
            self.fixture_definition(ROOT / "tests", name="beta-lab"))
        with patch("monotools.apps.discover_apps", return_value=definitions):
            with self.assertRaises(AppDefinitionError) as raised:
                get_app("missing")
        self.assertEqual(
            str(raised.exception),
            "unknown app 'missing'; available: alpha-lab, beta-lab",
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

    def test_document_frontends_build_as_self_contained_documents(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="document-") as temporary:
            directory = Path(temporary) / "sample-lab"
            frontend = directory / "frontend"
            frontend.mkdir(parents=True)
            frontend.joinpath("index.html").write_text(
                "<title>Sample</title><style>main { color: red; }</style>"
                "<body><main>Ready</main><script>window.ready = true;</script></body>",
                encoding="utf-8",
            )
            definition = self.fixture_definition(directory)
            build_app(definition, ROOT)
            validate_dist(definition)
            document = definition.dist_directory.joinpath("index.html").read_text(encoding="utf-8")

            self.assertEqual([path.name for path in definition.dist_directory.iterdir()], ["index.html"])
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

    def test_lit_type_error_is_actionable_before_build_mutation(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="lit-error-") as temporary:
            definition = self.fixture_definition(Path(temporary), format_name="lit")
            output = definition.dist_directory / "index.html"
            output.parent.mkdir()
            before = b"stable artifact"
            output.write_bytes(before)
            failed = Mock(returncode=1,
                stdout="tests/frontend/nested/broken.ts:3:7 - error TS2322")

            with patch("monotools.lifecycle.subprocess.run", return_value=failed):
                with self.assertRaisesRegex(LifecycleError, "nested/broken.ts.*TS2322"):
                    from monotools.lifecycle import _validate_lit
                    _validate_lit(definition, ROOT)
            self.assertEqual(output.read_bytes(), before)

    def test_console_panes_have_bounded_scroll_and_title_controls(self) -> None:
        shell = (ROOT / "monotools" / "frontend.py").read_text(encoding="utf-8")
        components = (ROOT / "packages" / "lit-ui" / "src" / "index.ts").read_text(
            encoding="utf-8"
        )
        compact_components = " ".join(components.split())

        self.assertIn(".pane-body { min-height: 0; overflow: auto; }", shell)
        self.assertIn(".body { min-height: 0; overflow: auto; }", compact_components)
        self.assertIn('slot[name="title-end"] { display: flex;', compact_components)

    def test_console_command_buttons_reverse_their_shadow_when_pressed(self) -> None:
        shell = (ROOT / "monotools" / "frontend.py").read_text(encoding="utf-8")
        components = (ROOT / "packages" / "lit-ui" / "src" / "index.ts").read_text(
            encoding="utf-8"
        )
        compact_components = " ".join(components.split())

        self.assertIn("transform: translateY(1px)", shell)
        self.assertIn("linear-gradient(#45413f, #302d2b)", shell)
        self.assertIn("linear-gradient(#242220, #181716)", shell)
        self.assertIn("inset 0 3px 3px #0e0f0f, inset 0 -1px #504945", shell)
        pressed_rule = 'button:active:not(:disabled), button[aria-pressed="true"]:not(:disabled)'
        self.assertIn(pressed_rule, compact_components)
        self.assertIn("linear-gradient(#4a4643, #35312f)", components)
        self.assertIn("var(--console-button-border, #c6b58f)", components)
        self.assertIn("var(--console-button-border-hover, #f0dfb8)", components)
        self.assertIn("transform: translateY(1px)", components)
        self.assertIn("linear-gradient(#242220, #181716)", components)
        self.assertIn("inset 0 3px 4px rgb(0 0 0 / 0.65)", components)
        self.assertIn("inset 0 -1px rgb(255 255 255 / 0.08)", components)
        self.assertNotIn("transition:", components)

    def test_lit_apps_share_recessed_control_and_overlay_treatment(self) -> None:
        styles = (ROOT / "packages" / "lit-ui" / "src" / "styles.ts").read_text(
            encoding="utf-8"
        )
        compact_styles = " ".join(styles.split())

        self.assertIn('input[type="checkbox"] {', compact_styles)
        self.assertIn('input[type="checkbox"]:checked::before', compact_styles)
        self.assertIn('textarea { border-radius: 3px; resize: none;', compact_styles)
        self.assertIn('[role="dialog"] { border-radius: 4px; }', compact_styles)


if __name__ == "__main__":
    unittest.main()
