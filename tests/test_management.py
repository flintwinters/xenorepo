"""Contracts for reusable Typer-native manager construction."""

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess
import sys
import unittest
from unittest.mock import ANY, patch

import typer
from typer.testing import CliRunner

from monotools.apps import AppDefinitionError, ROOT
from monotools.management import create_app_cli, create_app_manager, create_cli, resolve_local_app
import manage as repository_manager


class ManagementTests(unittest.TestCase):
    def _definition(self, directory: Path, name: str) -> None:
        directory.mkdir(parents=True)
        (directory / "frontend").mkdir()
        (directory / "backend").mkdir()
        (directory / "app.yaml").write_text(
            f"""name: {name}
title: {name.title()}
module: apps.{name}.backend.server
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

    def _manager(self, *, include_serve: bool = True, ui_suite: str | None = None):
        temporary = TemporaryDirectory(dir=ROOT / "tests", prefix="manager-")
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        name = directory.name
        (directory / "frontend").mkdir()
        (directory / "backend").mkdir()
        (directory / "app.yaml").write_text(
            f"""name: {name}
title: Fixture
module: apps.{name}.backend.server
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
        (directory / "tests").mkdir()
        if ui_suite is not None:
            ui_suite = f"tests/{ui_suite}"
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

    def test_root_mounts_the_complete_immediate_manager_inventory_in_order(self) -> None:
        definitions = [definition for definition, _ in repository_manager.MANAGERS]

        expected = [directory.name for directory in sorted(repository_manager.APPS_DIRECTORY.iterdir())
            if directory.is_dir() and (directory / "manage.py").is_file()]
        self.assertEqual([definition.name for definition in definitions], expected)
        result = CliRunner().invoke(repository_manager.app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        for definition in definitions:
            self.assertIn(definition.name, result.output)

    def test_root_cockpit_cold_start_discovers_the_complete_inventory(self) -> None:
        """Prove the real entrypoint imports before in-process test fixtures can mask it."""
        result = subprocess.run(
            [sys.executable, "manage.py", "list"],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for definition, _ in repository_manager.MANAGERS:
            self.assertIn(definition.name, result.stdout)

    def test_root_and_leaf_commands_have_distinct_ownership(self) -> None:
        root_commands = {command.name or command.callback.__name__.replace("_", "-")
            for command in repository_manager.app.registered_commands}
        self.assertEqual(root_commands,
            {"bootstrap", "list", "status", "check", "test", "ui-check", "verify"})

        mounted_name = repository_manager.MANAGERS[0][0].name
        result = CliRunner().invoke(repository_manager.app, [mounted_name, "--help"])
        self.assertEqual(result.exit_code, 0)
        for command in ("build", "check", "test", "serve", "ui-check"):
            self.assertIn(command, result.output)
        self.assertNotIn("bootstrap", result.output)
        self.assertNotIn("status", result.output)

    def test_targeted_check_executes_only_the_selected_application(self) -> None:
        selected = repository_manager.MANAGERS[0][0]
        with patch("monotools.management.validate_app") as validate, \
             patch("monotools.management.build_app") as build, \
             patch("monotools.management.validate_dist") as validate_dist:
            result = CliRunner().invoke(repository_manager.app, [selected.name, "check"])

        self.assertEqual(result.exit_code, 0)
        validate.assert_called_once_with(selected, ROOT)
        build.assert_called_once_with(selected, ROOT)
        validate_dist.assert_called_once_with(selected)

    def test_root_check_executes_every_application_once_in_stable_order(self) -> None:
        with patch("manage.validate_app") as validate, patch("manage.build_app") as build, \
             patch("manage.validate_dist") as validate_dist:
            result = CliRunner().invoke(repository_manager.app, ["check"])

        self.assertEqual(result.exit_code, 0)
        definitions = [definition for definition, _ in repository_manager.MANAGERS]
        self.assertEqual([call.args[0] for call in validate.call_args_list], definitions)
        self.assertEqual([call.args[0] for call in build.call_args_list], definitions)
        self.assertEqual([call.args[0] for call in validate_dist.call_args_list], definitions)

    def test_root_test_executes_the_curated_suite_once(self) -> None:
        with patch("manage.run_test_suite", return_value=0) as run, \
             patch("manage.run_browser_framework_suite", return_value=0) as browser:
            result = CliRunner().invoke(repository_manager.app, ["test"])

        self.assertEqual(result.exit_code, 0)
        expected = [ROOT / "tests"] + [manager.python_suite.path
            for _, manager in repository_manager.MANAGERS]
        self.assertEqual([call.args for call in run.call_args_list],
            [(ROOT, suite) for suite in expected])
        self.assertEqual(len(expected), len(set(expected)))
        browser.assert_called_once_with(ROOT)

    def test_verify_composes_checks_tests_and_complete_browser_inventory(self) -> None:
        with patch("manage.check") as check, patch("manage.test") as test, \
             patch("manage.ui_check") as browser:
            result = CliRunner().invoke(repository_manager.app, ["verify"])
        self.assertEqual(result.exit_code, 0)
        check.assert_called_once_with()
        test.assert_called_once_with()
        browser.assert_called_once_with(app_name=None, evidence=False)

    def test_discovery_rejects_unmanaged_and_invalid_manager_directories(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="inventory-") as temporary:
            apps_directory = Path(temporary) / "apps"
            unmanaged = apps_directory / "unmanaged"
            self._definition(unmanaged, "unmanaged")
            with self.assertRaisesRegex(repository_manager.ManagerError, "has no manage.py"):
                repository_manager.discover_managers(apps_directory)

            (unmanaged / "manage.py").write_text("app = object()\n", encoding="utf-8")
            with self.assertRaisesRegex(repository_manager.ManagerError, "must export 'manager'"):
                repository_manager.discover_managers(apps_directory)

            (unmanaged / "manage.py").write_text("raise RuntimeError('broken manager')\n",
                encoding="utf-8")
            with self.assertRaisesRegex(repository_manager.ManagerError, "broken manager"):
                repository_manager.discover_managers(apps_directory)

    def test_specification_only_apps_are_visible_but_not_active(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="inventory-") as temporary:
            apps_directory = Path(temporary) / "apps"
            planned = apps_directory / "future"
            planned.mkdir(parents=True)
            (planned / "SPEC.md").write_text("# Future\n", encoding="utf-8")

            self.assertEqual(repository_manager.discover_managers(apps_directory), ())
            with patch.object(repository_manager, "APPS_DIRECTORY", apps_directory):
                listed = CliRunner().invoke(repository_manager.app, ["list"])
                status = CliRunner().invoke(repository_manager.app, ["status"])
            self.assertEqual(listed.exit_code, 0)
            self.assertIn("future", listed.output)
            self.assertIn("planned", listed.output)
            self.assertEqual(status.exit_code, 0)
            self.assertIn("future", status.output)

            (planned / "README.md").write_text("incomplete\n", encoding="utf-8")
            with self.assertRaisesRegex(repository_manager.ManagerError, "has no manage.py"):
                repository_manager.discover_managers(apps_directory)

    def test_manager_rejects_absolute_escaping_and_non_test_suite_paths(self) -> None:
        _, manage_file = self._manager()
        for path in (ROOT / "tests", "../tests", "frontend"):
            with self.subTest(path=path), self.assertRaisesRegex(
                    AppDefinitionError, "app-owned|beneath tests"):
                create_app_manager(manage_file, tests=path)

    def test_specified_app_requires_an_owned_product_browser_journey(self) -> None:
        _, manage_file = self._manager()
        (manage_file.parent / "SPEC.md").write_text(
            "# Product\n\nA shippable journey.\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(AppDefinitionError, "no app-owned browser suite"):
            create_app_manager(manage_file, tests="tests")

        manager = create_app_manager(
            manage_file, tests="tests", ui_suite="tests/product.spec.js"
        )
        self.assertEqual(manager.browser_suite.path, manage_file.parent / "tests/product.spec.js")

    def test_root_and_mounted_managers_are_working_directory_independent(self) -> None:
        original = Path.cwd()
        foreign = ROOT / "tests"
        try:
            os.chdir(foreign)
            root_result = CliRunner().invoke(repository_manager.app, ["list"])
            definition, manager = repository_manager.MANAGERS[0]
            leaf_result = CliRunner().invoke(repository_manager.app,
                [definition.name, "serve", "--help"])
        finally:
            os.chdir(original)

        self.assertEqual(root_result.exit_code, 0)
        self.assertIn(definition.name, root_result.output)
        self.assertEqual(leaf_result.exit_code, 0)
        self.assertEqual(resolve_local_app(manager.definition.directory / "manage.py"), definition)


if __name__ == "__main__":
    unittest.main()
