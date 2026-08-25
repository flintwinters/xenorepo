"""Calculator-owned product contracts."""

import unittest

from monotools.apps import ROOT, get_app
from monotools.lifecycle import build_app


class CalculatorTests(unittest.TestCase):
    def test_visible_work_persists_in_the_self_contained_artifact(self) -> None:
        definition = get_app("calculator")
        build_app(definition, ROOT)
        source = (definition.directory / definition.artifact("index").source).read_text()
        document = (definition.dist_directory / "index.html").read_text()
        self.assertIn('storageKey = "calc98-state-v1"', source)
        self.assertIn("localStorage.setItem(storageKey", source)
        self.assertIn("localStorage.getItem(storageKey)", source)
        self.assertIn("calc98-state-v1", document)
        self.assertNotIn('src="', document)


if __name__ == "__main__":
    unittest.main()
