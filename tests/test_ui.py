"""Tests for the centralized browser-check lifecycle."""

import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from monotools.orchestration.apps import ROOT
from monotools.orchestration.aesthetics import DEFAULT_MODEL, review_aesthetics, screenshot_inventory
from monotools.orchestration.ui import available_local_port, run_ui_check, ui_artifact_directory
from tests.support import synthetic_app_definition


class BrowserLifecycleTests(unittest.TestCase):
    def test_ui_artifacts_are_visible_and_app_owned(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="ui-app-") as temporary:
            definition = synthetic_app_definition(Path(temporary))
            self.assertEqual(ui_artifact_directory(definition),
                definition.directory / "data" / "ui-check")

    def test_available_port_is_a_valid_loopback_port(self) -> None:
        listener = Mock()
        listener.__enter__ = Mock(return_value=listener)
        listener.__exit__ = Mock(return_value=False)
        listener.getsockname.return_value = ("127.0.0.1", 8123)
        with patch("monotools.orchestration.ui.socket.socket", return_value=listener) as factory:
            self.assertEqual(available_local_port(), 8123)
        factory.assert_called_once()

    def test_runner_uses_the_built_service_and_preserves_app_artifacts(self) -> None:
        process = Mock(spec=subprocess.Popen)
        process.pid = 4200
        with TemporaryDirectory(dir=ROOT / "tests", prefix="ui-app-") as app_temporary, \
             TemporaryDirectory(dir=ROOT / "tests", prefix="ui-artifacts-") as temporary:
            definition = synthetic_app_definition(Path(app_temporary),
                capabilities=frozenset({"database"}))
            artifacts = Path(temporary)
            suite = definition.directory / "tests" / "e2e" / "journey.spec.js"
            with patch("monotools.orchestration.ui.validate_app") as validate, \
                 patch("monotools.orchestration.browser.validate_browser_suite", return_value={"counts": {}}), \
                 patch("monotools.orchestration.ui.build_app") as build, \
                 patch("monotools.orchestration.ui.validate_dist") as validate_dist, \
                 patch("monotools.orchestration.ui.ui_artifact_directory", return_value=artifacts), \
                 patch("monotools.orchestration.ui.available_local_port", return_value=8123), \
                 patch("monotools.orchestration.ui.subprocess.Popen", return_value=process) as popen, \
                 patch("monotools.orchestration.ui.wait_for_health") as health, \
                 patch("monotools.orchestration.ui._run_browser", return_value=0) as run, \
                 patch("monotools.orchestration.ui._terminate", return_value="clean"):
                actual = run_ui_check(
                    definition, ROOT, suite, update_snapshots=True
                )
                summary = __import__("json").loads((artifacts / "summary.json").read_text())

        self.assertEqual(actual, artifacts)
        validate.assert_called_once_with(definition, ROOT)
        build.assert_called_once_with(definition, ROOT)
        validate_dist.assert_called_once_with(definition)
        health.assert_called_once_with(8123, process)
        self.assertEqual(
            popen.call_args.args[0][:4],
            [__import__("sys").executable, "-m", "uvicorn", definition.module + ":app"],
        )
        database_key = f"{definition.name.upper()}_DATABASE_URL"
        self.assertEqual(popen.call_args.kwargs["env"][database_key],
            f"sqlite:///{artifacts / 'browser.db'}")
        self.assertEqual(run.call_args.args[0], [
            str(ROOT / "node_modules" / ".bin" / "playwright"), "test",
            "tests/browser-framework/universal.spec.js",
            str(suite.relative_to(ROOT)),
            "--update-snapshots",
        ])
        self.assertEqual(run.call_args.args[2]["BASE_URL"], "http://127.0.0.1:8123")
        self.assertEqual(run.call_args.args[2][database_key],
            f"sqlite:///{artifacts / 'browser.db'}")
        self.assertEqual(summary["cleanup"], "clean")
        self.assertEqual(summary["browserStatus"], 0)

    def test_runner_supports_route_smoke_checks_without_an_app_suite(self) -> None:
        process = Mock(spec=subprocess.Popen)
        process.pid = 4201
        with TemporaryDirectory(dir=ROOT / "tests", prefix="ui-app-") as app_temporary, \
             TemporaryDirectory(dir=ROOT / "tests", prefix="ui-artifacts-") as temporary, \
             patch("monotools.orchestration.browser.validate_browser_suite",
                return_value={"counts": {"browser-integration": 1}}), \
             patch("monotools.orchestration.ui.validate_app"), patch("monotools.orchestration.ui.build_app"), \
             patch("monotools.orchestration.ui.validate_dist"), \
             patch("monotools.orchestration.ui.ui_artifact_directory", return_value=Path(temporary)), \
             patch("monotools.orchestration.ui.available_local_port", return_value=8124), \
             patch("monotools.orchestration.ui.subprocess.Popen", return_value=process), \
             patch("monotools.orchestration.ui.wait_for_health"), \
             patch("monotools.orchestration.ui._run_browser", return_value=0) as run, \
             patch("monotools.orchestration.ui._terminate", return_value="clean"):
            definition = synthetic_app_definition(Path(app_temporary))
            run_ui_check(definition, ROOT)
        self.assertEqual(run.call_args.args[0][-1], "tests/browser-framework/universal.spec.js")
        self.assertNotIn("--update-snapshots", run.call_args.args[0])

    def test_screenshot_inventory_requires_every_resolution_for_each_route(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="aesthetic-evidence-") as temporary:
            directory = Path(temporary)
            for route in ("root", "settings"):
                for label, resolution in (("desktop", "1440x1000"),
                        ("tablet", "768x1024"), ("phone", "390x844")):
                    (directory / f"{route}--{label}--{resolution}.png").write_bytes(b"png")
            self.assertEqual(len(screenshot_inventory(directory)), 6)
            (directory / "settings--phone--390x844.png").unlink()
            with self.assertRaisesRegex(Exception, "settings missing 390x844"):
                screenshot_inventory(directory)

    def test_ai_review_uses_images_and_persists_structured_verdict(self) -> None:
        response = {"id": "resp_test", "model": "vision-test", "choices": [{"message": {
            "content": json.dumps({
                "verdict": "pass", "summary": "Cohesive.", "findings": [],
            })}}], "usage": {"total_tokens": 42, "cost": 0.01}}
        opened = Mock()
        opened.__enter__ = Mock(return_value=opened)
        opened.__exit__ = Mock(return_value=False)
        opened.read.side_effect = [json.dumps(response).encode("utf-8"), b""]
        with TemporaryDirectory(dir=ROOT / "tests", prefix="aesthetic-review-") as temporary:
            directory = Path(temporary)
            screenshots = directory / "screenshots"
            screenshots.mkdir()
            for label, resolution in (("desktop", "1440x1000"),
                    ("tablet", "768x1024"), ("phone", "390x844")):
                (screenshots / f"root--{label}--{resolution}.png").write_bytes(b"png")
            definition = synthetic_app_definition(directory)
            report_path = directory / "review.json"
            hygiene = {"schemaVersion": 1, "app": definition.name, "hardViolationCount": 0,
                "violations": [], "metrics": {"borders": 2, "gaps": 1}}
            (directory / "ui-hygiene.json").write_text(json.dumps(hygiene), encoding="utf-8")
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "secret"}), \
                 patch("monotools.orchestration.aesthetics.urllib.request.urlopen",
                    return_value=opened) as urlopen:
                report = review_aesthetics(definition, screenshots, report_path)
            request_body = json.loads(urlopen.call_args.args[0].data)
            image_inputs = request_body["messages"][0]["content"][1:]
            prompt = request_body["messages"][0]["content"][0]["text"]
            self.assertEqual(len(image_inputs), 3)
            self.assertTrue(all(item["image_url"]["url"].startswith("data:image/png;base64,")
                for item in image_inputs))
            self.assertTrue(request_body["provider"]["require_parameters"])
            self.assertEqual(request_body["response_format"]["type"], "json_schema")
            finding_schema = request_body["response_format"]["json_schema"]["schema"] \
                ["properties"]["findings"]
            self.assertEqual(finding_schema["maxItems"], 6)
            self.assertIn("viewport", finding_schema["items"]["required"])
            self.assertEqual(request_body["model"], "z-ai/glm-5.3-flash")
            self.assertEqual(request_body["model"], DEFAULT_MODEL)
            self.assertEqual(request_body["reasoning"], {"effort": "low"})
            self.assertEqual(request_body["max_tokens"], 4096)
            self.assertIn("gratuitous box nesting", prompt)
            self.assertIn("responsive layouts", prompt)
            self.assertIn('"hardViolationCount": 0', prompt)
            self.assertNotIn("App-owned visual brief", prompt)
            self.assertEqual(report["verdict"], "pass")
            self.assertEqual(report["schemaVersion"], 4)
            self.assertEqual(report["uiHygiene"], hygiene)
            self.assertEqual(report["gateway"], "openrouter")
            self.assertEqual(report["usage"]["cost"], 0.01)
            self.assertEqual(json.loads(report_path.read_text())["responseId"], "resp_test")


if __name__ == "__main__":
    unittest.main()
