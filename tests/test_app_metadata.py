"""Typed lifecycle metadata contracts shared by every monoapp.

The fixtures exercise declaration failures before manager imports or lifecycle
mutation can obscure the owning app.yaml field.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from monotools.orchestration.apps import AppDefinitionError, ROOT, load_app


BASE = """name: fixture
title: Fixture
module: apps.fixture.backend.server
testing:
  python: tests
  browser:
    suite: tests/e2e/readiness.spec.ts
    proofs: [acceptance, visual]
frontend:
  artifacts:
    index:
      format: preact
      source: frontend/index.tsx
      output: index.html
  routes:
    /: index
"""


class AppMetadataTests(unittest.TestCase):
    def fixture(self, temporary: str, contents: str = BASE) -> Path:
        directory = Path(temporary) / "fixture"
        (directory / "frontend").mkdir(parents=True)
        (directory / "backend").mkdir()
        (directory / "tests/e2e").mkdir(parents=True)
        (directory / "manage.py").touch()
        (directory / "app.yaml").write_text(contents, encoding="utf-8")
        return directory

    def test_testing_metadata_is_typed_and_defaults_to_the_platform_viewports(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="testing-metadata-") as temporary:
            testing = load_app(self.fixture(temporary)).testing

        self.assertIsNotNone(testing)
        self.assertEqual(testing.python_suite, Path("tests"))
        self.assertEqual(testing.browser_suite, Path("tests/e2e/readiness.spec.ts"))
        self.assertEqual(testing.proof_kinds, frozenset({"acceptance", "visual"}))
        self.assertEqual(testing.viewports,
            frozenset({"wide-viewport-chromium", "narrow-viewport-chromium"}))

    def test_testing_metadata_rejects_missing_malformed_and_unsafe_declarations(self) -> None:
        cases = (
            (BASE.replace("testing:\n", "checks:\n"), "unknown keys: checks"),
            (BASE.replace("  python: tests", "  python: ../tests"), "normalized relative path"),
            (BASE.replace("  python: tests", "  python: frontend"), "must be beneath tests"),
            (BASE.replace("tests/e2e/readiness.spec.ts", "frontend/readiness.spec.ts"),
                "must be beneath tests"),
            (BASE.replace("    proofs: [acceptance, visual]", "    proofs: acceptance"),
                "proofs must be a list"),
            (BASE.replace("[acceptance, visual]", "[visual, acceptance]"),
                "proofs must be unique and sorted"),
            (BASE.replace("[acceptance, visual]", "[acceptance, audit]"),
                "proofs has unsupported values: audit"),
            (BASE.replace("[acceptance, visual]", "[]"), "proofs must not be empty"),
            (BASE.replace("    proofs: [acceptance, visual]",
                "    proofs: [acceptance, visual]\n    input_modalities: [gesture]"),
                "input_modalities has unsupported values: gesture"),
        )
        with TemporaryDirectory(dir=ROOT / "tests", prefix="testing-metadata-") as temporary:
            for index, (contents, message) in enumerate(cases):
                with self.subTest(case=index):
                    directory = self.fixture(f"{temporary}/{index}", contents)
                    with self.assertRaisesRegex(AppDefinitionError, message):
                        load_app(directory)


if __name__ == "__main__":
    unittest.main()
