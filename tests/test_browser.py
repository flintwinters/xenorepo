"""Contracts for truthful, pre-mutation browser proof validation."""

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from monotools.orchestration.apps import ROOT
from monotools.orchestration.browser import validate_browser_suite
from monotools.orchestration.lifecycle import LifecycleError
from monotools.orchestration.management import BrowserSuite
from monotools.orchestration.ui import run_ui_check
from tests.support import synthetic_app_definition


class BrowserProofContractTests(unittest.TestCase):
    def test_universal_geometry_distinguishes_generic_and_domain_controls(self) -> None:
        source = (ROOT / "tests/browser-framework/universal.spec.js").read_text(encoding="utf-8")
        self.assertIn('element.getAttribute("data-ui-control") === "domain"', source)
        self.assertIn("innerWidth <= 390 ? 28 : 18", source)
        self.assertIn("generic control below ${minimum}px target", source)
        self.assertIn("text below 10px", source)
        self.assertIn("zero-size interactive control", source)
        self.assertIn("horizontally clipped control", source)

    def test_universal_route_check_is_not_mislabeled_product_acceptance(self) -> None:
        suite = BrowserSuite(
            ROOT / "tests/browser-framework/universal.spec.js",
            frozenset({"accessibility", "browser-integration"}),
        )

        report = validate_browser_suite(suite, ROOT)

        self.assertEqual(report["counts"]["acceptance"], 0)
        self.assertGreater(report["counts"]["browser-integration"], 0)
        self.assertGreater(report["counts"]["accessibility"], 0)
        self.assertGreater(report["counts"]["visual"], 0)

    def test_owned_suite_contract_parses_and_enumerates_required_proofs(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="browser-suite-") as temporary:
            path = Path(temporary) / "journey.spec.js"
            path.write_text(
                'const { expect, test } = require("@xenorepo/browser-testing");\n'
                'test("[acceptance] completes an invented journey", async ({ page }) => {\n'
                '  await page.goto("/");\n'
                '  const action = page.getByRole("button", { name: "Continue" });\n'
                '  await expect(action).toBeEnabled();\n'
                '  await action.click();\n'
                '  await expect(page.getByText("Complete")).toBeVisible();\n'
                '});\n',
                encoding="utf-8",
            )
            report = validate_browser_suite(
                BrowserSuite(path, frozenset({"acceptance"})), ROOT)

        self.assertGreater(report["tests"], 0)

    def test_static_validator_reports_stable_category_and_parse_errors(self) -> None:
        validator = ROOT / "packages" / "browser-testing" / "src" / "validate.js"
        cases = {
            "missing-tag.spec.ts": ('test("claim", async () => {});', "BROWSER_PROOF_TAG_COUNT"),
            "conflict.spec.ts": ('test("[acceptance] [visual] claim", async () => {});', "BROWSER_PROOF_TAG_COUNT"),
            "only.spec.ts": ('test.only("[acceptance] claim", async () => {});', "BROWSER_FORBID_ONLY"),
            "synthetic.spec.ts": ('test("[acceptance] touch", async ({page}) => {'
                'await page.dispatchEvent("x", "pointerdown");});', "BROWSER_UNTRUSTED_ACCEPTANCE"),
            "malformed.spec.ts": ('test("[acceptance] broken", async ( => {});', "BROWSER_PARSE_ERROR"),
        }
        with TemporaryDirectory(dir=ROOT / "tests", prefix="browser-contract-") as temporary:
            for filename, (contents, code) in cases.items():
                with self.subTest(case=filename):
                    path = Path(temporary) / filename
                    path.write_text(contents, encoding="utf-8")
                    result = subprocess.run(
                        ["node", str(validator), str(path)], check=False,
                        text=True, capture_output=True, cwd=ROOT,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(code, result.stderr)

    def test_static_failure_occurs_before_build_database_or_service_mutation(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="browser-app-") as temporary:
            definition = synthetic_app_definition(Path(temporary))
            with patch("monotools.orchestration.browser.validate_browser_suite",
                    side_effect=LifecycleError("BROWSER_PROOF_TAG_COUNT: bad")), \
                 patch("monotools.orchestration.ui.validate_app") as validate, \
                 patch("monotools.orchestration.ui.build_app") as build, \
                 patch("monotools.orchestration.ui.subprocess.Popen") as start:
                with self.assertRaisesRegex(LifecycleError, "BROWSER_PROOF_TAG_COUNT"):
                    run_ui_check(definition, ROOT, BrowserSuite(Path("bad")))
        validate.assert_not_called()
        build.assert_not_called()
        start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
