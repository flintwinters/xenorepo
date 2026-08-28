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
        self.assertIn("profile recorded", source.lower())
        self.assertIn('<div class="pane-body"><ol class="review-list"', source)
        document = definition.dist_directory.joinpath("index.html").read_text()
        self.assertIn('meta name="monotools-shell" content="console"', document)


if __name__ == "__main__":
    unittest.main()
