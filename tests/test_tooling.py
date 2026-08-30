import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from fastapi import FastAPI

from monotools.orchestration.apps import AppDefinition, AppDefinitionError, FrontendArtifact, ROOT, get_app, load_app
from monotools.orchestration.lifecycle import (
    LifecycleError,
    _validate_runtime_contract,
    build_app,
    validate_source_lines,
)
from monotools.runtime.application import create_application
from monotools.orchestration.watch import frontend_inputs, watch_frontend


class RepositoryAppTests(unittest.TestCase):
    def fixture_definition(self, directory: Path, *, name: str = "sample-lab") -> AppDefinition:
        return AppDefinition(
            name=name,
            title="Sample Laboratory",
            directory=directory,
            module=f"apps.{name}.backend.server",
            artifacts=(FrontendArtifact("index", "preact", Path("frontend/index.tsx"),
                Path("index.html")),),
            routes=(("/", "index"),),
            capabilities=frozenset(),
        )

    def test_source_line_validation_covers_programs_and_stylesheets(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="source-lines-") as temporary:
            workspace = Path(temporary)
            source = workspace / "apps" / "fixture"
            source.mkdir(parents=True)
            python = source / "example.py"
            javascript = source / "example.js"
            typescript = source / "example.ts"
            stylesheet = source / "example.css"
            python.write_text("answer = 42\n", encoding="utf-8")
            javascript.write_text("export const answer = 42;\n", encoding="utf-8")
            typescript.write_text("export const answer = 42;\n", encoding="utf-8")
            stylesheet.write_text(".answer { color: green; }\n", encoding="utf-8")

            validate_source_lines(workspace)
            python.write_text(f'value = "{"p" * 121}"\n', encoding="utf-8")
            javascript.write_text(f'const value = "{"j" * 121}";\n', encoding="utf-8")
            typescript.write_text(f'const value = "{"t" * 121}";\n', encoding="utf-8")
            stylesheet.write_text(f'.value {{ content: "{"c" * 121}"; }}\n', encoding="utf-8")

            with self.assertRaisesRegex(
                LifecycleError,
                r"apps/fixture/example\.css:1: 144 characters \(maximum 120\)[\s\S]*"
                r"apps/fixture/example\.js:1: 138 characters \(maximum 120\)[\s\S]*"
                r"apps/fixture/example\.py:1: 131 characters \(maximum 120\)[\s\S]*"
                r"apps/fixture/example\.ts:1: 138 characters \(maximum 120\)",
            ):
                validate_source_lines(workspace)

    def test_preact_build_inlines_imported_css_and_javascript(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="preact-build-") as temporary:
            directory = Path(temporary)
            frontend = directory / "frontend"
            frontend.mkdir()
            (frontend / "index.css").write_text(".fixture { color: rgb(1, 2, 3); }\n", encoding="utf-8")
            (frontend / "index.tsx").write_text(
                'import { render } from "preact";\nimport "./index.css";\n'
                'export function mount(root: HTMLElement) { render(<p class="fixture">Ready</p>, root); }\n',
                encoding="utf-8",
            )
            definition = AppDefinition(
                name="fixture", title="Fixture", directory=directory, module="fixture.server",
                artifacts=(FrontendArtifact("index", "preact", Path("frontend/index.tsx"),
                    Path("index.html")),), routes=(("/", "index"),), capabilities=frozenset(),
            )

            build_app(definition, ROOT)

            document = (directory / "dist" / "index.html").read_text(encoding="utf-8")
            self.assertIn(".fixture{color:#010203}", document)
            self.assertIn("Ready", document)
            self.assertNotIn('script src=', document)
            self.assertNotIn('rel="stylesheet"', document)

    def test_preact_metadata_requires_a_tsx_entry(self) -> None:
        base = """name: fixture
title: Fixture
module: apps.fixture.backend.server
frontend:
  artifacts:
    index:
      format: preact
      source: frontend/index.tsx
      output: index.html
  routes:
    /: index
"""
        with TemporaryDirectory(dir=ROOT / "tests", prefix="preact-metadata-") as temporary:
            directory = Path(temporary) / "fixture"
            (directory / "frontend").mkdir(parents=True)
            (directory / "backend").mkdir()
            (directory / "manage.py").touch()
            (directory / "app.yaml").write_text(base, encoding="utf-8")
            self.assertEqual(load_app(directory).artifacts[0].format, "preact")
            (directory / "app.yaml").write_text(base.replace("index.tsx", "index.ts"), encoding="utf-8")
            with self.assertRaisesRegex(AppDefinitionError, "preact.*must end in .tsx"):
                load_app(directory)

    def test_preact_diagnostics_preserve_the_existing_dist_artifact(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="preact-error-") as temporary:
            directory = Path(temporary)
            frontend = directory / "frontend"
            frontend.mkdir()
            (frontend / "index.tsx").write_text(
                "export function mount(root: HTMLElement) { const broken: number = 'text'; root.remove(); }\n",
                encoding="utf-8",
            )
            definition = AppDefinition(
                name="fixture", title="Fixture", directory=directory, module="fixture.server",
                artifacts=(FrontendArtifact("index", "preact", Path("frontend/index.tsx"),
                    Path("index.html")),), routes=(("/", "index"),), capabilities=frozenset(),
            )
            output = directory / "dist" / "index.html"
            output.parent.mkdir()
            output.write_text("stable", encoding="utf-8")
            from monotools.orchestration.lifecycle import _validate_frontend

            with self.assertRaisesRegex(LifecycleError, "Type 'string' is not assignable to type 'number'"):
                _validate_frontend(definition, ROOT)
            self.assertEqual(output.read_text(encoding="utf-8"), "stable")

    def test_openapi_declaration_is_filtered_and_idempotent(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="openapi-") as temporary:
            directory = Path(temporary)
            application = FastAPI()

            @application.get("/api/items/{item_id}")
            def item(item_id: int) -> dict[str, int]:
                return {"item_id": item_id}

            @application.get("/health")
            def health() -> dict[str, str]:
                return {"status": "ok"}

            definition = AppDefinition(
                name="fixture", title="Fixture", directory=directory, module="fixture.server",
                artifacts=(), routes=(), capabilities=frozenset(),
            )
            from monotools.orchestration.lifecycle import _generate_openapi_types

            _generate_openapi_types(definition, application, ROOT)
            first = (directory / "data" / "openapi.d.ts").read_bytes()
            _generate_openapi_types(definition, application, ROOT)
            schema = (directory / "data" / "openapi.json").read_text(encoding="utf-8")
            self.assertEqual((directory / "data" / "openapi.d.ts").read_bytes(), first)
            self.assertIn('"/api/items/{item_id}"', schema)
            self.assertNotIn('"/health"', schema)

    def test_frontend_watch_includes_css_tooling_and_shared_ui(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="preact-watch-") as temporary:
            directory = Path(temporary)
            frontend = directory / "frontend"
            frontend.mkdir()
            (frontend / "index.tsx").touch()
            (frontend / "index.css").touch()
            definition = AppDefinition(
                name="fixture", title="Fixture", directory=directory, module="fixture.server",
                artifacts=(FrontendArtifact("index", "preact", Path("frontend/index.tsx"),
                    Path("index.html")),), routes=(("/", "index"),), capabilities=frozenset(),
            )
            inputs = frontend_inputs(definition, ROOT)
            self.assertIn(frontend / "index.css", inputs)
            self.assertIn(ROOT / "monotools" / "node" / "build-preact.mjs", inputs)
            self.assertIn(ROOT / "monotools" / "node" / "check-frontend.mjs", inputs)
            self.assertIn(ROOT / "tsconfig.preact.json", inputs)

    def test_library_catalog_describes_the_shared_frontend_and_backend_boundaries(self) -> None:
        catalog = (ROOT / "LIBRARIES.md").read_text(encoding="utf-8")

        self.assertIn("# Custom Library Catalog", catalog)
        self.assertIn("`monotools/`", catalog)
        self.assertIn("`packages/ui/`", catalog)
        self.assertIn("Applications are consumers; they do not", catalog)
        self.assertIn("import one another.", catalog)

    def test_frontend_watch_rebuilds_declared_inputs(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="watch-") as temporary:
            directory = Path(temporary) / "sample-lab"
            frontend = directory / "frontend"
            frontend.mkdir(parents=True)
            (frontend / "index.tsx").touch()
            (frontend / "feature.ts").touch()
            definition = self.fixture_definition(directory)
            inputs = frontend_inputs(definition, ROOT)

            self.assertIn(frontend / "index.tsx", inputs)
            self.assertIn(frontend / "feature.ts", inputs)
            self.assertIn(ROOT / "tsconfig.preact.json", inputs)
            report = Mock()
            with patch("monotools.orchestration.watch._snapshot", side_effect=[
                    ((Path("source"), 1),), ((Path("source"), 2),)
                ]), patch("monotools.orchestration.watch.build_app") as rebuild, patch(
                    "monotools.orchestration.watch.time.sleep", side_effect=[None, RuntimeError("stop")]
                ):
                with self.assertRaisesRegex(RuntimeError, "stop"):
                    watch_frontend(definition, ROOT, report, interval=0)
            rebuild.assert_called_once_with(definition, ROOT)
            report.assert_called_once_with("Rebuilt sample-lab frontend")

    def test_unknown_app_error_reports_discovered_catalog(self) -> None:
        definitions = (self.fixture_definition(ROOT / "tests", name="alpha-lab"),
            self.fixture_definition(ROOT / "tests", name="beta-lab"))
        with patch("monotools.orchestration.apps.discover_apps", return_value=definitions):
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
      format: preact
      source: frontend/index.tsx
      output: index.html
  routes:
    /: index
"""
        cases = {
            "malformed": ("name: [\n", "malformed YAML"),
            "duplicate": (base.replace("title: Fixture\n", "title: Fixture\ntitle: Again\n"), "duplicate key"),
            "unknown-artifact": (base.replace("/: index", "/: missing"), "unknown frontend artifact"),
            "reserved-health-route": (base.replace("/: index", "/health: index"),
                "reserved by the platform"),
            "reserved-agent-tools-route": (base.replace("/: index", "/agent/tools: index"),
                "reserved by the platform"),
            "invalid-output": (base.replace("output: index.html", "output: ../index.html"), "normalized relative path"),
            "authored-html": (base.replace("frontend/index.tsx", "frontend/index.html"),
                r"preact frontend artifact source must end in .tsx"),
            "legacy-format": (base.replace("format: preact", "format: lit"),
                "frontend format must be 'preact', got 'lit'"),
            "document-format": (base.replace("format: preact", "format: document"),
                "frontend format must be 'preact', got 'document'"),
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
      format: preact
      source: frontend/index.tsx
      output: index.html
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
                            "source: frontend/index.tsx", "source: index.tsx")
                    (directory / "app.yaml").write_text(contents, encoding="utf-8")
                    with self.assertRaisesRegex(AppDefinitionError, message):
                        load_app(directory)

    def test_runtime_registers_one_independent_artifact_endpoint_per_metadata_route(self) -> None:
        definition = AppDefinition(
            name="fixture",
            title="Fixture pages",
            directory=ROOT / "tests",
            module="tests.fixture",
            artifacts=(
                FrontendArtifact("home", "preact", Path("frontend/home.tsx"), Path("home.html")),
                FrontendArtifact("about", "preact", Path("frontend/about.tsx"), Path("about.html")),
            ),
            routes=(("/", "home"), ("/about", "about")),
            capabilities=frozenset(),
        )
        with patch("monotools.runtime.application.get_app", return_value=definition):
            application = create_application("fixture")
        routes = {route.path: route for route in application.routes if hasattr(route, "path")}
        self.assertEqual(routes["/"].endpoint(), ROOT / "tests" / "dist" / "home.html")
        self.assertEqual(routes["/about"].endpoint(), ROOT / "tests" / "dist" / "about.html")
        self.assertEqual(routes["/health"].endpoint(), {"status": "ok"})

    def test_runtime_contract_requires_the_platform_agent_registry(self) -> None:
        definition = self.fixture_definition(ROOT / "tests")
        module = Mock(app=FastAPI())
        with self.assertRaisesRegex(LifecycleError, "/agent/tools registry"):
            _validate_runtime_contract(definition, module)

        with patch("monotools.runtime.application.get_app", return_value=definition):
            module.app = create_application(definition.name)
        _validate_runtime_contract(definition, module)

    def test_frontend_type_error_is_actionable_before_build_mutation(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="frontend-error-") as temporary:
            definition = self.fixture_definition(Path(temporary))
            output = definition.dist_directory / "index.html"
            output.parent.mkdir()
            before = b"stable artifact"
            output.write_bytes(before)
            failed = Mock(returncode=1,
                stdout="tests/frontend/nested/broken.ts:3:7 - error TS2322")

            with patch("monotools.orchestration.lifecycle.subprocess.run", return_value=failed):
                with self.assertRaisesRegex(LifecycleError, "nested/broken.ts.*TS2322"):
                    from monotools.orchestration.lifecycle import _validate_frontend
                    _validate_frontend(definition, ROOT)
            self.assertEqual(output.read_bytes(), before)

    def test_console_panes_have_bounded_scroll_and_title_controls(self) -> None:
        styles = (ROOT / "packages" / "ui" / "src" / "styles.css").read_text(
            encoding="utf-8")
        components = (ROOT / "packages" / "ui" / "src" / "index.tsx").read_text(
            encoding="utf-8")
        compact_styles = " ".join(styles.split())

        self.assertIn(".x-ui-pane-body { min-height: 0; overflow: auto; }", compact_styles)
        self.assertIn('class="x-ui-title-end"', components)

    def test_content_height_panes_never_create_vertical_scrollports(self) -> None:
        styles = (ROOT / "packages" / "ui" / "src" / "styles.css").read_text(
            encoding="utf-8")
        components = (ROOT / "packages" / "ui" / "src" / "index.tsx").read_text(
            encoding="utf-8")
        compact_styles = " ".join(styles.split())

        self.assertIn('contentHeight ? "x-ui-pane-content-height"', components)
        self.assertIn(".x-ui-pane-content-height { grid-template-rows: auto auto; }",
            compact_styles)
        self.assertIn((".x-ui-pane-content-height > .x-ui-pane-body { "
            "overflow: visible; }"), compact_styles)

    def test_console_command_buttons_reverse_their_shadow_when_pressed(self) -> None:
        styles = (ROOT / "packages" / "ui" / "src" / "styles.css").read_text(
            encoding="utf-8")
        compact_styles = " ".join(styles.split())

        pressed_rule = ('.x-ui-command-control:active:not(:disabled), '
            '.x-ui-command-control[aria-pressed="true"]:not(:disabled)')
        self.assertIn(pressed_rule, compact_styles)
        self.assertIn("linear-gradient(#4a4643, #35312f)", styles)
        self.assertIn("var(--console-button-border, #c6b58f)", styles)
        self.assertIn("var(--console-button-border-hover, #f0dfb8)", styles)
        self.assertIn("transform: translateY(1px)", styles)
        self.assertIn("linear-gradient(#242220, #181716)", styles)
        self.assertIn("inset 0 3px 4px rgb(0 0 0 / 0.65)", styles)
        self.assertIn("inset 0 -1px rgb(255 255 255 / 0.08)", styles)
        self.assertNotIn("transition:", styles)


if __name__ == "__main__":
    unittest.main()
