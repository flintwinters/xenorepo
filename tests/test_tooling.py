from pathlib import Path
import unittest

from tooling.apps import AppDefinitionError, discover_apps, get_app


from tooling.lifecycle import build_app, validate_app, validate_dist


class CalculatorRepositoryTests(unittest.TestCase):
    def test_calculator_is_discovered_with_document_frontend(self) -> None:
        apps = discover_apps()
        self.assertEqual([app.name for app in apps], ["calculator"])
        self.assertEqual(apps[0].frontend_format, "document")

    def test_unknown_app_error_reports_empty_catalog(self) -> None:
        with self.assertRaisesRegex(
            AppDefinitionError, "unknown app 'missing'; available: calculator"
        ):
            get_app("missing")

    def test_calculator_validates_and_builds_one_document(self) -> None:
        definition = get_app("calculator")
        validate_app(definition)
        build_app(definition)
        validate_dist(definition)
        assets = [path.name for path in definition.dist_directory.iterdir() if path.is_file()]
        self.assertEqual(assets, ["index.html"])
        document = (definition.dist_directory / "index.html").read_text(encoding="utf-8")
        self.assertIn("<style>", document)
        self.assertIn("<script>", document)
        self.assertNotIn('src="', document)
        self.assertNotIn('href="', document)


if __name__ == "__main__":
    unittest.main()
