"""Tests for the centralized browser-check lifecycle."""

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from monotools.apps import AppDefinition, ROOT, get_app
from monotools.lifecycle import LifecycleError
from monotools.ui import available_local_port, run_ui_check, ui_artifact_directory


class BrowserLifecycleTests(unittest.TestCase):
    def test_ui_artifacts_are_visible_and_app_owned(self) -> None:
        definition = get_app("rps")

        self.assertEqual(
            ui_artifact_directory(definition),
            definition.directory / "data" / "ui-check",
        )

    def test_available_port_is_a_valid_loopback_port(self) -> None:
        listener = Mock()
        listener.__enter__ = Mock(return_value=listener)
        listener.__exit__ = Mock(return_value=False)
        listener.getsockname.return_value = ("127.0.0.1", 8123)
        with patch("monotools.ui.socket.socket", return_value=listener) as factory:
            self.assertEqual(available_local_port(), 8123)
        factory.assert_called_once()

    def test_runner_uses_the_built_service_and_preserves_app_artifacts(self) -> None:
        definition = get_app("rps")
        process = Mock(spec=subprocess.Popen)
        process.pid = 4200
        with TemporaryDirectory(dir=ROOT / "apps" / "rps" / "data", prefix="ui-test-") as temporary:
            artifacts = Path(temporary)
            with patch("monotools.ui.validate_app") as validate, \
                 patch("monotools.browser.validate_browser_suite", return_value={"counts": {}}), \
                 patch("monotools.ui.build_app") as build, \
                 patch("monotools.ui.validate_dist") as validate_dist, \
                 patch("monotools.ui.ui_artifact_directory", return_value=artifacts), \
                 patch("monotools.ui.available_local_port", return_value=8123), \
                 patch("monotools.ui.subprocess.Popen", return_value=process) as popen, \
                 patch("monotools.ui.wait_for_health") as health, \
                 patch("monotools.ui._run_browser", return_value=0) as run, \
                 patch("monotools.ui._terminate", return_value="clean"):
                actual = run_ui_check(
                    definition, ROOT, definition.directory / "tests" / "e2e" / "arena.spec.js"
                )
                summary = __import__("json").loads((artifacts / "summary.json").read_text())

        self.assertEqual(actual, artifacts)
        validate.assert_called_once_with(definition, ROOT)
        build.assert_called_once_with(definition, ROOT)
        validate_dist.assert_called_once_with(definition)
        health.assert_called_once_with(8123, process)
        self.assertEqual(
            popen.call_args.args[0][:4],
            [__import__("sys").executable, "-m", "uvicorn", "apps.rps.backend.server:app"],
        )
        self.assertEqual(popen.call_args.kwargs["env"]["RPS_DATABASE_URL"],
            f"sqlite:///{artifacts / 'browser.db'}")
        self.assertEqual(run.call_args.args[0], [
            str(ROOT / "node_modules" / ".bin" / "playwright"), "test",
            "tests/browser-framework/universal.spec.js",
            "apps/rps/tests/e2e/arena.spec.js",
        ])
        self.assertEqual(run.call_args.args[2]["BASE_URL"], "http://127.0.0.1:8123")
        self.assertEqual(run.call_args.args[2]["RPS_DATABASE_URL"],
            f"sqlite:///{artifacts / 'browser.db'}")
        self.assertEqual(summary["cleanup"], "clean")
        self.assertEqual(summary["browserStatus"], 0)

    def test_runner_supports_universal_journeys_without_an_app_suite(self) -> None:
        definition = get_app("calculator")
        process = Mock(spec=subprocess.Popen)
        process.pid = 4201
        with TemporaryDirectory(dir=definition.directory, prefix="ui-test-") as temporary, \
             patch("monotools.browser.validate_browser_suite",
                return_value={"counts": {"acceptance": 1}}), \
             patch("monotools.ui.validate_app"), patch("monotools.ui.build_app"), \
             patch("monotools.ui.validate_dist"), \
             patch("monotools.ui.ui_artifact_directory", return_value=Path(temporary)), \
             patch("monotools.ui.available_local_port", return_value=8124), \
             patch("monotools.ui.subprocess.Popen", return_value=process), \
             patch("monotools.ui.wait_for_health"), \
             patch("monotools.ui._run_browser", return_value=0) as run, \
             patch("monotools.ui._terminate", return_value="clean"):
            run_ui_check(definition, ROOT)
        self.assertEqual(run.call_args.args[0][-1], "tests/browser-framework/universal.spec.js")


if __name__ == "__main__":
    unittest.main()
