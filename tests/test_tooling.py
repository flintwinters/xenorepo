import unittest
import subprocess
from pathlib import Path

from tooling.apps import discover_apps, get_app
from tooling.lifecycle import build_app, validate_app, validate_dist


class CalculatorAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_app(get_app("calculator"))

    def test_calculator_is_discoverable_and_valid(self) -> None:
        names = [definition.name for definition in discover_apps()]
        self.assertEqual(names, ["calculator"])
        validate_app(get_app("calculator"))

    def test_calculator_build_contains_runtime_assets(self) -> None:
        validate_dist(get_app("calculator"))

    def test_compiled_calculator_performs_chained_arithmetic(self) -> None:
        module = (Path.cwd() / "apps/calculator/dist/calculator.js").as_uri()
        script = f"""
            import {{ Calculator }} from {module!r};
            const calculator = new Calculator();
            calculator.inputDigit('1');
            calculator.inputDigit('2');
            calculator.chooseOperator('+');
            calculator.inputDigit('3');
            calculator.chooseOperator('×');
            calculator.inputDigit('2');
            calculator.calculate();
            if (calculator.display() !== '30') process.exit(1);
        """
        subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
