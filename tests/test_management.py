"""Contracts for reusable Typer-native manager construction."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import ANY, patch

import typer
from typer.testing import CliRunner

from monotools.apps import ROOT
from monotools.management import create_app_cli, create_cli, resolve_local_app


class ManagementTests(unittest.TestCase):
    def _manager(self, *, include_serve: bool = True, ui_suite: str | None = None):
        temporary = TemporaryDirectory(dir=ROOT / "tests", prefix="manager-")
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        name = directory.name
        (directory / "app.yaml").write_text(
            f"""name: {name}
title: Fixture
module: tests.fixture
frontend:
  artifacts:
    index:
      format: document
      source: frontend/index.html
      output: index.html
      shell: console
  routes:
    /: index
""",
            encoding="utf-8",
        )
        manage_file = directory / "manage.py"
        manage_file.touch()
        return create_app_cli(manage_file, tests="tests", ui_suite=ui_suite,
            include_serve=include_serve), manage_file

    def test_plain_cli_has_no_repository_or_fastapi_requirements(self) -> None:
        app = create_cli("Independent commands.")

        self.assertIsInstance(app, typer.Typer)
        self.assertEqual(app.info.help, "Independent commands.")
        self.assertEqual(app.registered_commands, [])

    def test_local_definition_is_resolved_from_manager_directory(self) -> None:
        app, manage_file = self._manager()

        self.assertIsInstance(app, typer.Typer)
        self.assertEqual(resolve_local_app(manage_file).directory, manage_file.parent)

    def test_standard_app_commands_are_conditional_and_typer_native(self) -> None:
        app, _ = self._manager(include_serve=False, ui_suite="browser.spec.js")
        result = CliRunner().invoke(app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        command_names = {command.name or command.callback.__name__.replace("_", "-")
            for command in app.registered_commands}
        self.assertEqual(command_names, {"build", "check", "test", "ui-check"})

    def test_standard_serve_delegates_to_shared_lifecycle(self) -> None:
        app, manage_file = self._manager()
        definition = resolve_local_app(manage_file)
        with patch("monotools.management.serve_app", return_value=0) as serve:
            result = CliRunner().invoke(app, ["serve", "--host", "0.0.0.0", "--port", "8123"])

        self.assertEqual(result.exit_code, 0)
        serve.assert_called_once_with(definition, definition.directory.parent.parent,
            host="0.0.0.0", port=8123, watch=False,
            report=ANY)


if __name__ == "__main__":
    unittest.main()
