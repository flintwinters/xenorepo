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
        completed = Mock(returncode=0)
        with TemporaryDirectory(dir=ROOT / "apps" / "rps" / "data", prefix="ui-test-") as temporary:
            artifacts = Path(temporary)
            with patch("monotools.ui.validate_app") as validate, \
                 patch("monotools.ui.build_app") as build, \
                 patch("monotools.ui.validate_dist") as validate_dist, \
                 patch("monotools.ui.ui_artifact_directory", return_value=artifacts), \
                 patch("monotools.ui.available_local_port", return_value=8123), \
                 patch("monotools.ui.subprocess.Popen", return_value=process) as popen, \
                 patch("monotools.ui.wait_for_health") as health, \
                 patch("monotools.ui.subprocess.run", return_value=completed) as run, \
                 patch("monotools.ui._terminate", return_value=None):
                actual = run_ui_check(definition)

        self.assertEqual(actual, artifacts)
        validate.assert_called_once_with(definition)
        build.assert_called_once_with(definition)
        validate_dist.assert_called_once_with(definition)
        health.assert_called_once_with(8123, process)
        self.assertEqual(
            popen.call_args.args[0][:4],
            ["uv", "run", "uvicorn", "apps.rps.server:app"],
        )
        self.assertEqual(run.call_args.args[0], [
            str(ROOT / "node_modules" / ".bin" / "playwright"), "test", "tests/ui/rps.spec.js",
        ])
        self.assertEqual(run.call_args.kwargs["env"]["BASE_URL"], "http://127.0.0.1:8123")
        self.assertEqual(run.call_args.kwargs["env"]["RPS_DATABASE_URL"],
            f"sqlite:///{artifacts / 'browser.db'}")

    def test_runner_requires_an_app_specific_suite(self) -> None:
        definition = AppDefinition(
            "missing-ui", "Missing UI", Path("apps/missing-ui"), "tests.fixture", (), (), frozenset()
        )
        with patch("monotools.ui.validate_app"), patch("monotools.ui.build_app"), \
             patch("monotools.ui.validate_dist"):
            with self.assertRaisesRegex(LifecycleError, "has no browser suite"):
                run_ui_check(definition)


if __name__ == "__main__":
    unittest.main()
