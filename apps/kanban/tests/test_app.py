"""Kanban walking-skeleton contract."""

import unittest

from monotools.orchestration.apps import ROOT, get_app
from monotools.orchestration.lifecycle import build_app


class ApplicationTests(unittest.TestCase):
    def test_build_is_a_self_contained_preact_document(self) -> None:
        definition = get_app("kanban")
        build_app(definition, ROOT)
        document = definition.document_for_route("/").read_text(encoding="utf-8")
        self.assertIn("Kanban", document)
        self.assertNotIn('src="', document)
        self.assertNotIn('rel="stylesheet"', document)


if __name__ == "__main__":
    unittest.main()
