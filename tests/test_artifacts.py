"""Universal contracts for built monoapp artifacts.

These tests keep platform-owned document invariants out of individual monoapp
suites while exercising the validator used by every root and leaf check.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from monotools.orchestration.apps import AppDefinition, FrontendArtifact, ROOT
from monotools.orchestration.lifecycle import LifecycleError, run_test_suite, validate_dist


class ArtifactContractTests(unittest.TestCase):
    def definition(self, directory: Path) -> AppDefinition:
        return AppDefinition(
            name="fixture", title="Fixture", directory=directory, module="fixture.server",
            artifacts=(FrontendArtifact("index", "preact", Path("frontend/index.tsx"),
                Path("index.html")),),
            routes=(("/", "index"),), capabilities=frozenset(),
        )

    def test_dist_validation_owns_self_containment_and_artifact_identity(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="dist-contract-") as temporary:
            definition = self.definition(Path(temporary))
            definition.dist_directory.mkdir()
            document = definition.document_for_route("/")
            marker = '<meta name="xenorepo-artifact" content="index.html">'
            document.write_text(f"<html><head>{marker}</head></html>", encoding="utf-8")
            validate_dist(definition)
            invalid_documents = (
                ('<script src="app.js"></script>', "external script or stylesheet"),
                ('<link href="app.css" rel="stylesheet">', "external script or stylesheet"),
                ("<html></html>", "artifact identity marker"),
            )
            for invalid, message in invalid_documents:
                with self.subTest(document=invalid):
                    document.write_text(invalid, encoding="utf-8")
                    with self.assertRaisesRegex(LifecycleError, message):
                        validate_dist(definition)

    def test_dist_validation_reports_every_missing_declared_artifact(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="dist-missing-") as temporary:
            definition = self.definition(Path(temporary))
            with self.assertRaisesRegex(LifecycleError, "build did not produce: index.html"):
                validate_dist(definition)

    def test_app_python_suites_may_be_empty_without_masking_failures(self) -> None:
        with patch("monotools.orchestration.lifecycle.subprocess.run") as run:
            run.return_value.returncode = 5
            self.assertEqual(run_test_suite(ROOT, ROOT / "tests", allow_empty=True), 0)
            self.assertEqual(run_test_suite(ROOT, ROOT / "tests"), 5)
            run.return_value.returncode = 1
            self.assertEqual(run_test_suite(ROOT, ROOT / "tests"), 1)


if __name__ == "__main__":
    unittest.main()
