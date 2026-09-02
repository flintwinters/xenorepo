"""Calculator delivery contract."""

import unittest

from monotools.orchestration.apps import ROOT, get_app
from monotools.orchestration.lifecycle import build_app
from apps.calculator.backend.server import app


class ApplicationTests(unittest.TestCase):
    def test_build_is_a_self_contained_preact_document(self) -> None:
        definition = get_app("calculator")
        build_app(definition, ROOT)
        document = definition.document_for_route("/").read_text(encoding="utf-8")
        self.assertIn("Calculator", document)
        self.assertIn("Basic calculator", document)
        self.assertIn("Calculator display", document)
        self.assertNotIn('src="', document)
        self.assertNotIn('rel="stylesheet"', document)

    def test_runtime_exposes_no_stateful_calculator_api(self) -> None:
        routes = {route.path for route in app.routes}
        self.assertFalse(any(path.startswith("/api/") for path in routes))


if __name__ == "__main__":
    unittest.main()
