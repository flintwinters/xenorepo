import unittest

from tooling.apps import AppDefinitionError, discover_apps, get_app


class EmptyRepositoryTests(unittest.TestCase):
    def test_no_apps_are_discovered(self) -> None:
        self.assertEqual(discover_apps(), ())

    def test_unknown_app_error_reports_empty_catalog(self) -> None:
        with self.assertRaisesRegex(
            AppDefinitionError, "unknown app 'missing'; available: none"
        ):
            get_app("missing")


if __name__ == "__main__":
    unittest.main()
