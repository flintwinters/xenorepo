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

from monotools.orchestration import apps as app_registry
from monotools.orchestration.apps import AppDefinitionError, ROOT
from monotools.orchestration.audit import AuditReport, AuditViolation
from monotools.orchestration.management import create_app_manager, create_cli, resolve_local_app
from monotools.orchestration.repositories import (
    AppRepositoryState,
    RepositoryError,
    declared_app_submodules,
    promote_to_submodule,
    uninitialized_app_submodules,
)
from monotools.orchestration.scaffolding import ScaffoldError, scaffold_app
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
      format: preact
      source: frontend/index.tsx
      output: index.html
  routes:
    /: index
""",
            encoding="utf-8",
        )

    def _manager(self, *, include_serve: bool = True, ui_suite: str | None = None):
        temporary = TemporaryDirectory(dir=ROOT / "tests", prefix="manager-")
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name) / "fixture"
        name = directory.name
        (directory / "frontend").mkdir(parents=True)
        (directory / "backend").mkdir()
        (directory / "app.yaml").write_text(
            f"""name: {name}
title: Fixture
module: apps.{name}.backend.server
frontend:
  artifacts:
    index:
      format: preact
      source: frontend/index.tsx
      output: index.html
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
        manager = create_app_manager(manage_file, tests="tests", ui_suite=ui_suite,
            include_serve=include_serve)
        return manager.app, manage_file

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
        self.assertEqual(command_names, {"build", "check", "test", "ui-check", "verify"})
        self.assertEqual({group.name for group in app.registered_groups}, {"git"})

    def test_standard_serve_delegates_to_shared_lifecycle(self) -> None:
        app, manage_file = self._manager()
        definition = resolve_local_app(manage_file)
        with patch("monotools.orchestration.management.serve_app", return_value=0) as serve:
            result = CliRunner().invoke(app, ["serve", "--host", "0.0.0.0", "--port", "8123"])

        self.assertEqual(result.exit_code, 0)
        serve.assert_called_once_with(definition, ROOT,
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

    def test_active_monoapp_readmes_link_to_xenorepo_at_the_top(self) -> None:
        link = "[Xenorepo on GitHub](https://github.com/flintwinters/xenorepo)"
        for definition, _ in repository_manager.MANAGERS:
            with self.subTest(app=definition.name):
                lines = (definition.directory / "README.md").read_text(encoding="utf-8").splitlines()
                self.assertEqual(lines[2], link)

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
            {"audit", "bootstrap", "list", "status", "check", "test", "ui-check", "verify"})
        self.assertIn("monoapp", {group.name for group in repository_manager.app.registered_groups})

        mounted_name = repository_manager.MANAGERS[0][0].name
        result = CliRunner().invoke(repository_manager.app, [mounted_name, "--help"])
        self.assertEqual(result.exit_code, 0)
        for command in ("build", "check", "test", "serve", "ui-check", "verify"):
            self.assertIn(command, result.output)
        self.assertNotIn("bootstrap", result.output)
        self.assertNotIn("status", result.output)

    def test_root_audit_reports_zero_architecture_and_structural_debt(self) -> None:
        result = CliRunner().invoke(repository_manager.app, ["audit"], color=False)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Architecture violations: 0", result.output)
        self.assertIn("0 large file(s)", result.output)
        self.assertRegex(result.output, r"0 complex\s+function\(s\)")

    def test_targeted_check_executes_only_the_selected_application(self) -> None:
        selected = repository_manager.MANAGERS[0][0]
        with patch("monotools.orchestration.management.validate_app") as validate, \
             patch("monotools.orchestration.management.build_app") as build, \
             patch("monotools.orchestration.management.validate_dist") as validate_dist:
            result = CliRunner().invoke(repository_manager.app, [selected.name, "check"])

        self.assertEqual(result.exit_code, 0)
        validate.assert_called_once_with(selected, ROOT)
        build.assert_called_once_with(selected, ROOT)
        validate_dist.assert_called_once_with(selected)

    def test_root_check_executes_every_application_once_in_stable_order(self) -> None:
        with patch("manage.validate_app") as validate, patch("manage.build_app") as build, \
             patch("manage.validate_dist") as validate_dist, \
             patch("manage.uninitialized_app_submodules", return_value=()), \
             patch("manage.discover_managers", return_value=repository_manager.MANAGERS):
            result = CliRunner().invoke(repository_manager.app, ["check"])

        self.assertEqual(result.exit_code, 0, result.output)
        definitions = [definition for definition, _ in repository_manager.MANAGERS]
        self.assertEqual([call.args[0] for call in validate.call_args_list], definitions)
        self.assertEqual([call.args[0] for call in build.call_args_list], definitions)
        self.assertEqual([call.args[0] for call in validate_dist.call_args_list], definitions)

    def test_root_check_rejects_every_structural_violation_category_before_building(self) -> None:
        categories = (
            ("architecture", "central-app-identity"),
            ("large_files", "large-file"),
            ("complex_functions", "complex-function"),
        )
        for field, category in categories:
            with self.subTest(category=category):
                violation = AuditViolation(category, "fixture/source.py:1", "fixture violation")
                values = {name: () for name, _ in categories}
                values[field] = (violation,)
                report = AuditReport(**values)
                with patch("manage._collect_audit", return_value=report), \
                     patch("manage.uninitialized_app_submodules", return_value=()), \
                     patch("manage.validate_app") as validate, \
                     patch("manage.build_app") as build:
                    result = CliRunner().invoke(repository_manager.app, ["check"], color=False)

                self.assertEqual(result.exit_code, 1)
                self.assertIn("structural audit failed:", result.output)
                self.assertIn(f"{category} fixture/source.py:1:", result.output)
                self.assertIn("fixture violation", " ".join(result.output.split()))
                validate.assert_not_called()
                build.assert_not_called()

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

    def test_declared_uninitialized_submodules_ignore_stale_generated_files(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="submodules-") as temporary:
            workspace = Path(temporary)
            apps_directory = workspace / "apps"
            bleb = apps_directory / "bleb"
            bleb.mkdir(parents=True)
            (workspace / ".gitmodules").write_text(
                '[submodule "bleb"]\n\tpath = apps/bleb\n\turl = git@example.test:bleb.git\n',
                encoding="utf-8",
            )

            self.assertEqual(declared_app_submodules(workspace), (bleb,))
            self.assertEqual(uninitialized_app_submodules(workspace), (bleb,))
            self.assertEqual(repository_manager.discover_managers(apps_directory), ())
            (bleb / "data").mkdir()
            (bleb / "data/cache.json").write_text("{}\n", encoding="utf-8")
            self.assertEqual(uninitialized_app_submodules(workspace), (bleb,))
            self.assertEqual(repository_manager.discover_managers(apps_directory), ())
            with patch.object(app_registry, "APPS_DIRECTORY", apps_directory):
                self.assertEqual(app_registry.discover_apps(), ())

            (bleb / ".git").write_text("gitdir: ../../.git/modules/apps/bleb\n",
                encoding="utf-8")
            self.assertEqual(uninitialized_app_submodules(workspace), ())
            with self.assertRaisesRegex(repository_manager.ManagerError, "has no manage.py"):
                repository_manager.discover_managers(apps_directory)

    def test_manager_rejects_absolute_escaping_and_non_test_suite_paths(self) -> None:
        _, manage_file = self._manager()
        for path in (ROOT / "tests", "../tests", "frontend"):
            with self.subTest(path=path), self.assertRaisesRegex(
                    AppDefinitionError, "app-owned|beneath tests"):
                create_app_manager(manage_file, tests=path)

    def test_scaffolder_creates_a_complete_valid_app_without_overwriting(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="scaffold-") as temporary:
            apps_directory = Path(temporary) / "apps"
            directory = scaffold_app(apps_directory, "signal_lab", "Signal Lab")

            definition = repository_manager.load_app(directory)
            self.assertEqual(definition.name, "signal_lab")
            self.assertEqual(definition.title, "Signal Lab")
            self.assertTrue((directory / "SPEC.md").is_file())
            self.assertTrue((directory / ".gitignore").is_file())
            self.assertTrue((directory / "frontend/styles.css").is_file())
            self.assertTrue((directory / "tests/e2e/readiness.spec.ts").is_file())
            readme = (directory / "README.md").read_text(encoding="utf-8")
            self.assertEqual(readme.splitlines()[2],
                "[Xenorepo on GitHub](https://github.com/flintwinters/xenorepo)")
            self.assertNotIn("{{app_name}}", (directory / "app.yaml").read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ScaffoldError, "refusing to overwrite"):
                scaffold_app(apps_directory, "signal_lab", "Again")

    def test_scaffolder_rejects_non_importable_names_and_empty_titles(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="scaffold-") as temporary:
            apps_directory = Path(temporary) / "apps"
            for name, title, message in (
                ("Bad-Name", "Title", "app name must start"),
                ("valid_name", " ", "title must not be empty"),
            ):
                with self.subTest(name=name), self.assertRaisesRegex(ScaffoldError, message):
                    scaffold_app(apps_directory, name, title)

    def test_repository_promotion_requires_explicit_valid_github_identity(self) -> None:
        definition = repository_manager.MANAGERS[0][0]
        for owner, repository, visibility, message in (
            ("bad/owner", "app", "private", "owner"),
            ("owner", "bad/repo", "private", "repository"),
            ("owner", "app", "secret", "visibility"),
        ):
            with self.subTest(owner=owner, repository=repository, visibility=visibility), \
                    self.assertRaisesRegex(RepositoryError, message):
                promote_to_submodule(definition, ROOT, owner=owner, repository=repository,
                    visibility=visibility, verify=lambda: None)

    def test_repository_promotion_orders_history_remote_submodule_and_verification(self) -> None:
        definition = repository_manager.MANAGERS[0][0]
        split = "a" * 40
        calls: list[tuple[tuple[str, ...], Path]] = []

        def command(arguments: list[str], cwd: Path) -> str:
            calls.append((tuple(arguments), cwd))
            joined = " ".join(arguments)
            if "ls-files --stage" in joined:
                return "100644 b app.yaml"
            if "status --short" in joined:
                return ""
            if "diff --cached --name-only" in joined:
                return ""
            if "subtree split" in joined:
                return split
            if arguments[:3] == ["gh", "repo", "view"]:
                return "git@github.com:owner/app.git"
            if arguments[-3:] == ["rev-parse", "HEAD"] or joined.endswith("rev-parse HEAD"):
                return split
            return ""

        verified: list[str] = []
        state = AppRepositoryState("monolith", True, None, "current")
        with patch("monotools.orchestration.repositories.shutil.which", return_value="/usr/bin/tool"), \
             patch("monotools.orchestration.repositories.inspect_app_repository", return_value=state), \
             patch("monotools.orchestration.repositories._run", side_effect=command):
            remote = promote_to_submodule(definition, ROOT, owner="owner", repository="app",
                visibility="private", verify=lambda: verified.append("verified"))

        self.assertEqual(remote, "git@github.com:owner/app.git")
        self.assertEqual(verified, ["verified", "verified"])
        commands = [" ".join(arguments) for arguments, _ in calls]
        self.assertLess(next(i for i, item in enumerate(commands) if "subtree split" in item),
            next(i for i, item in enumerate(commands) if "gh repo create" in item))
        self.assertLess(next(i for i, item in enumerate(commands) if "git push" in item),
            next(i for i, item in enumerate(commands) if "git rm -r" in item))
        self.assertIn("git submodule add", "\n".join(commands))
        self.assertTrue(commands[-1].startswith("git commit -m"))

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
