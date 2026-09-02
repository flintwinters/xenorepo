"""Calculator delivery contract."""

import unittest

from fastapi import HTTPException

from monotools.orchestration.apps import ROOT, get_app
from monotools.orchestration.lifecycle import build_app
from apps.calculator.backend.server import Calculation, app, calculate


class ApplicationTests(unittest.TestCase):
    def test_build_is_a_self_contained_monoform_document(self) -> None:
        definition = get_app("calculator")
        build_app(definition, ROOT)
        document = definition.document_for_route("/").read_text(encoding="utf-8")
        self.assertIn("Calculator", document)
        self.assertIn("Left Operand", document)
        self.assertIn("CALCULATE", document)
        self.assertNotIn('src="', document)
        self.assertNotIn('rel="stylesheet"', document)

    def test_api_performs_every_operation_without_retaining_state(self) -> None:
        examples = (("add", 4, 3, 7), ("subtract", 4, 3, 1),
            ("multiply", -4, 3, -12), ("divide", 7.5, 2.5, 3))
        for operator, left, right, expected in examples:
            value = Calculation(left_operand=left, operator=operator, right_operand=right)
            self.assertEqual(calculate(value).result, expected)

    def test_division_by_zero_marks_the_divisor(self) -> None:
        value = Calculation(left_operand=8, operator="divide", right_operand=0)
        with self.assertRaises(HTTPException) as raised:
            calculate(value)
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(raised.exception.detail[0]["loc"], ["body", "right_operand"])

    def test_api_declares_the_monoform_action(self) -> None:
        operation = app.openapi()["paths"]["/api/calculate"]["post"]
        self.assertEqual(operation["operationId"], "calculate")
        self.assertEqual(operation["x-monotools-monoform"]["kind"], "action")


if __name__ == "__main__":
    unittest.main()
