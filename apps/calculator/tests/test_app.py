"""Calculator-owned structural contracts."""

import unittest

from monotools.apps import ROOT, get_app
from monotools.lifecycle import build_app


class CalculatorTests(unittest.TestCase):
    def test_calculator_build_is_self_contained_preact(self) -> None:
        definition = get_app("calculator")
        build_app(definition, ROOT)
        document = definition.document_for_route("/").read_text(encoding="utf-8")
        self.assertIn('<meta name="monotools-shell" content="console">', document)
        self.assertIn("CALCULATOR", document)
        self.assertNotIn('src="', document)
        self.assertNotIn('rel="stylesheet"', document)


if __name__ == "__main__":
    unittest.main()
