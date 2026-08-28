"""Contracts for truthful, pre-mutation browser proof validation."""

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from monotools.apps import ROOT, get_app
from monotools.browser import validate_browser_suite
from monotools.lifecycle import LifecycleError
from monotools.management import BrowserSuite
from monotools.ui import run_ui_check


class BrowserProofContractTests(unittest.TestCase):
    def test_universal_route_check_is_not_mislabeled_product_acceptance(self) -> None:
        suite = BrowserSuite(
            ROOT / "tests/browser-framework/universal.spec.js",
            frozenset({"browser-integration"}),
        )

        report = validate_browser_suite(suite, ROOT)

        self.assertEqual(report["counts"]["acceptance"], 0)
        self.assertGreater(report["counts"]["browser-integration"], 0)

    def test_owned_suites_parse_and_enumerate_with_required_proofs(self) -> None:
        cases = (
            ("chat", "chat.spec.js"),
            ("kanban", "board.spec.ts"),
            ("rps", "arena.spec.js"),
            ("worminal", "desktop.spec.js"),
        )
        for app_name, filename in cases:
            with self.subTest(app=app_name):
                suite = BrowserSuite(
                    get_app(app_name).directory / "tests" / "e2e" / filename,
                    frozenset({"acceptance"}),
                )
                report = validate_browser_suite(suite, ROOT)
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
        definition = get_app("kanban")
        with patch("monotools.browser.validate_browser_suite",
                side_effect=LifecycleError("BROWSER_PROOF_TAG_COUNT: bad")), \
             patch("monotools.ui.validate_app") as validate, \
             patch("monotools.ui.build_app") as build, \
             patch("monotools.ui.subprocess.Popen") as start:
            with self.assertRaisesRegex(LifecycleError, "BROWSER_PROOF_TAG_COUNT"):
                run_ui_check(definition, ROOT, BrowserSuite(Path("bad")))
        validate.assert_not_called()
        build.assert_not_called()
        start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
