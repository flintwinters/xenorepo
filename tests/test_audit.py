"""Stable contracts for architecture and structural debt measurement."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from monotools.orchestration.apps import ROOT
from xenorepo.audit import audit_architecture, audit_workspace
from tests.support import synthetic_app_definition


class AuditTests(unittest.TestCase):
    def test_architecture_audit_finds_identity_import_and_shared_boundary_violations(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="audit-") as temporary:
            workspace = Path(temporary)
            first = workspace / "apps" / "orion"
            second = workspace / "apps" / "nebula"
            for directory in (first, second):
                (directory / "frontend").mkdir(parents=True)
                (directory / "backend").mkdir()
            (workspace / "monotools").mkdir()
            (workspace / "monotools" / "policy.py").write_text(
                '"""Describe synthetic policy.\n\nExplain its test-only purpose.\n"""\n'
                "from xenorepo.audit import audit_workspace\nproduct = 'orion'\n",
                encoding="utf-8")
            (first / "backend" / "server.py").write_text(
                "from apps.nebula.backend import server\n", encoding="utf-8")
            (first / "frontend" / "index.ts").write_text(
                'import "../../../packages/ui/src/index.js";\n',
                encoding="utf-8",
            )
            (first / "frontend" / "legacy.html").write_text("<p>authored HTML</p>\n",
                encoding="utf-8")
            (first / "frontend" / "legacy.js").write_text("export const legacy = true;\n",
                encoding="utf-8")
            (first / "dist").mkdir()
            (first / "dist" / "index.html").write_text("<p>compiled HTML</p>\n",
                encoding="utf-8")
            (second / "frontend" / "index.ts").write_text("export {};\n", encoding="utf-8")
            definitions = (
                synthetic_app_definition(first, name="orion"),
                synthetic_app_definition(second, name="nebula"),
            )

            violations = audit_architecture(workspace, definitions)

        self.assertEqual({item.category for item in violations}, {
            "central-app-identity", "cross-app-import", "frontend-boundary-import",
            "app-source-html", "legacy-frontend-javascript", "monotools-xenorepo-import",
        })
        html_violations = [item for item in violations if item.category == "app-source-html"]
        self.assertEqual([item.path for item in html_violations], ["apps/orion/frontend/legacy.html"])

    def test_structural_audit_reports_large_files_and_python_complexity(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="audit-") as temporary:
            workspace = Path(temporary)
            source = workspace / "monotools" / "large.py"
            source.parent.mkdir()
            decisions = "\n".join(f"    if value == {index}: return {index}" for index in range(9))
            source.write_text(
                f'"""Describe synthetic structure.\n\nExplain its audit purpose.\n"""\n'
                f"def decide(value):\n{decisions}\n" + "padding = None\n" * 587,
                encoding="utf-8",
            )

            report = audit_workspace(workspace, ())

        self.assertEqual(len(report.architecture), 0)
        self.assertEqual(len(report.large_files), 1)
        self.assertEqual(len(report.complex_functions), 1)
        self.assertIn("decide: 10", report.complex_functions[0].detail)

    def test_runtime_state_is_not_maintained_source(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="audit-") as temporary:
            workspace = Path(temporary)
            runtime = workspace / ".state" / "generated.py"
            runtime.parent.mkdir()
            runtime.write_text("\n".join("if value: pass" for _ in range(700)), encoding="utf-8")

            report = audit_workspace(workspace, ())

        self.assertEqual((report.large_files, report.complex_functions), ((), ()))

    def test_architecture_audit_requires_explanatory_monotools_docstrings(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="audit-") as temporary:
            workspace = Path(temporary)
            directory = workspace / "monotools"
            directory.mkdir()
            (directory / "missing.py").write_text("value = 1\n", encoding="utf-8")
            (directory / "shallow.py").write_text('"""Summary only."""\n', encoding="utf-8")
            (directory / "documented.py").write_text(
                '"""Useful summary.\n\nExplanation of the module boundary.\n"""\n', encoding="utf-8")

            violations = audit_architecture(workspace, ())

        self.assertEqual([(item.category, item.path) for item in violations], [
            ("monotools-module-documentation", "monotools/missing.py"),
            ("monotools-module-documentation", "monotools/shallow.py"),
        ])

    def test_architecture_audit_rejects_deliberately_stacked_table_cells(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="audit-") as temporary:
            workspace = Path(temporary)
            frontend = workspace / "apps" / "fixture" / "frontend"
            frontend.mkdir(parents=True)
            source = frontend / "index.ts"
            source.write_text("<td><strong>Name</strong><small>path</small></td>\n", encoding="utf-8")
            definition = synthetic_app_definition(frontend.parent, name="fixture")

            violations = audit_architecture(workspace, (definition,))

        self.assertEqual([(item.category, item.detail) for item in violations], [
            ("stacked-table-cell", "table cells must contain one logical value without stacked markup"),
        ])

    def test_repository_baseline_has_zero_structural_violations(self) -> None:
        import manage

        report = audit_workspace(ROOT, tuple(definition for definition, _ in manage.MANAGERS))

        self.assertEqual(report.architecture, ())
        self.assertEqual(report.large_files, ())
        self.assertEqual(report.complex_functions, ())


if __name__ == "__main__":
    unittest.main()
