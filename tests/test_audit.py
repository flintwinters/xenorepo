"""Stable contracts for architecture and structural debt measurement."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from monotools.apps import ROOT
from monotools.audit import audit_architecture, audit_workspace
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
            (workspace / "monotools" / "policy.py").write_text("product = 'orion'\n", encoding="utf-8")
            (first / "backend" / "server.py").write_text(
                "from apps.nebula.backend import server\n", encoding="utf-8")
            (first / "frontend" / "index.ts").write_text(
                'import "../../../packages/lit-ui/src/index.js";\n<x-proved><x-lonely>\n',
                encoding="utf-8",
            )
            (second / "frontend" / "index.ts").write_text("<x-proved>\n", encoding="utf-8")
            barrel = workspace / "packages" / "lit-ui" / "src" / "index.ts"
            barrel.parent.mkdir(parents=True)
            barrel.write_text(
                'customElements.define("x-proved", class extends HTMLElement {});\n'
                'customElements.define("x-lonely", class extends HTMLElement {});\n',
                encoding="utf-8",
            )
            definitions = (
                synthetic_app_definition(first, name="orion"),
                synthetic_app_definition(second, name="nebula"),
            )

            violations = audit_architecture(workspace, definitions)

        self.assertEqual({item.category for item in violations}, {
            "central-app-identity", "cross-app-import", "frontend-boundary-import",
            "unproved-custom-element",
        })

    def test_structural_audit_reports_large_files_and_python_complexity(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="audit-") as temporary:
            workspace = Path(temporary)
            source = workspace / "monotools" / "large.py"
            source.parent.mkdir()
            decisions = "\n".join(f"    if value == {index}: return {index}" for index in range(9))
            source.write_text(
                f"def decide(value):\n{decisions}\n" + "padding = None\n" * 591,
                encoding="utf-8",
            )

            report = audit_workspace(workspace, ())

        self.assertEqual(len(report.architecture), 0)
        self.assertEqual(len(report.large_files), 1)
        self.assertEqual(len(report.complex_functions), 1)
        self.assertIn("decide: 10", report.complex_functions[0].detail)

    def test_repository_baseline_has_zero_architecture_violations(self) -> None:
        import manage

        report = audit_workspace(ROOT, tuple(definition for definition, _ in manage.MANAGERS))

        self.assertEqual(report.architecture, ())
        self.assertEqual(len(report.large_files), 3)
        self.assertEqual(len(report.complex_functions), 17)
        self.assertTrue(all(item.path.startswith("apps/") for item in report.complex_functions))


if __name__ == "__main__":
    unittest.main()
