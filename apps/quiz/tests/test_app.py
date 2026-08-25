"""Quiz-owned product contracts."""

import unittest

from monotools.apps import ROOT, get_app
from monotools.lifecycle import build_app


class QuizTests(unittest.TestCase):
    def test_inventory_is_non_diagnostic_and_complete(self) -> None:
        definition = get_app("quiz")
        build_app(definition, ROOT)
        source = (definition.directory / definition.artifact("index").source).read_text()
        self.assertEqual(source.count("dimension:"), 8)
        self.assertIn("There are no right answers.", source)
        self.assertIn("NOT A CLINICAL ASSESSMENT", source)


if __name__ == "__main__":
    unittest.main()
