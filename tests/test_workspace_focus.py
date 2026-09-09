"""Contracts for focusing the current Xenorepo on one in-place monoapp workspace."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from typer.testing import CliRunner
from git import Repo

import manage
from monotools.orchestration.apps import ROOT
from monotools.provisioning.repositories import (
    AppBoundary, AppRepositoryState, RepositoryError, app_boundary_inventory,
    focus_app_workspace, initialize_app_submodules,
)


def _git(directory: Path, *arguments: str) -> str:
    if arguments[:1] == ("init",):
        Repo.init(Path(arguments[-1]), initial_branch="main")
        return ""
    return Repo(directory).git.execute(["git", *arguments]).strip()


class WorkspaceFocusTests(unittest.TestCase):
    def test_command_builds_before_focus_and_reports_only_after_promotion(self) -> None:
        selected = manage.MANAGERS[0][0]
        initial = AppRepositoryState("monolith", True, None, "current")
        final = AppRepositoryState("submodule", True, None, "current")
        only = (AppBoundary(selected.name, selected.directory, "submodule", True, True),)
        mutations = []
        with patch("manage._restore_toolchain", side_effect=lambda: mutations.append("restore")), \
             patch("manage.validate_app", side_effect=lambda *_: mutations.append("validate")), \
             patch("manage.build_app", side_effect=lambda *_: mutations.append("build")), \
             patch("manage.validate_dist"), \
             patch("manage.inspect_app_repository", side_effect=[initial, final]), \
             patch("manage._promote_monoapp", side_effect=lambda *_args, **_kwargs:
                mutations.append("promote")), \
             patch("manage.protect_upstream_remote", return_value=None), \
             patch("manage._focus_workspace", side_effect=lambda *_args, **_kwargs:
                mutations.append("focus")), \
             patch("manage.app_boundary_inventory", return_value=only):
            result = CliRunner().invoke(manage.app,
                ["monoapp", "fork-workspace", selected.name], input="y\n")

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(mutations, ["restore", "validate", "build", "focus", "promote"])
        self.assertIn("App workspace ready", result.output)

    def test_build_failure_withholds_every_source_mutation_and_success(self) -> None:
        selected = manage.MANAGERS[0][0]
        with patch("manage._restore_toolchain"), patch("manage.validate_app"), \
             patch("manage.build_app", side_effect=manage.LifecycleError("broken")), \
             patch("manage._focus_workspace") as focus, \
             patch("manage.protect_upstream_remote") as protect:
            result = CliRunner().invoke(manage.app,
                ["monoapp", "fork-workspace", selected.name])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertNotIn("App workspace ready", result.output)
        focus.assert_not_called()
        protect.assert_not_called()

    def test_complete_inventory_and_atomic_focus_need_no_submodule_network(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="focus-") as temporary:
            workspace = Path(temporary)
            _git(workspace.parent, "init", "--initial-branch=main", str(workspace))
            _git(workspace, "config", "user.email", "tests@example.test")
            _git(workspace, "config", "user.name", "Tests")
            (workspace / "apps").mkdir()
            for name in ("primary_app", "loaded_app"):
                directory = workspace / "apps" / name
                directory.mkdir()
                (directory / "manage.py").write_text(f"# {name}\n", encoding="utf-8")
            _git(workspace, "add", "apps")
            _git(workspace, "commit", "-m", "Add loaded apps")
            missing_revision = "1" * 40
            metadata = []
            for name in ("cold_app", "partial_app", "missing_app"):
                _git(workspace, "update-index", "--add", "--cacheinfo", "160000",
                    missing_revision, f"apps/{name}")
                metadata.append(
                    f'[submodule "{name}"]\npath=apps/{name}\nurl=https://unavailable.test/{name}\n')
            (workspace / ".gitmodules").write_text("".join(metadata), encoding="utf-8")
            _git(workspace, "add", ".gitmodules")
            _git(workspace, "commit", "-m", "Register unavailable apps")
            partial = workspace / "apps" / "partial_app"
            partial.mkdir()
            (partial / "recovery.txt").write_text("failed initialization\n", encoding="utf-8")

            inventory = app_boundary_inventory(workspace)
            self.assertEqual(tuple(item.name for item in inventory),
                ("cold_app", "loaded_app", "missing_app", "partial_app", "primary_app"))
            focused = focus_app_workspace(workspace, "primary_app", discard=True)

            self.assertEqual(focused.removed,
                ("cold_app", "loaded_app", "missing_app", "partial_app"))
            self.assertEqual(tuple(item.name for item in app_boundary_inventory(workspace)),
                ("primary_app",))
            self.assertFalse((workspace / ".gitmodules").exists())
            self.assertTrue((workspace / "apps" / "primary_app").is_dir())

    def test_initialization_uses_only_declared_requested_paths(self) -> None:
        with patch("monotools.provisioning.repositories.declared_app_submodules",
                return_value=(ROOT / "apps/signal_lab", ROOT / "apps/secondary_app")), \
             patch("monotools.provisioning.repositories._git") as git:
            initialize_app_submodules(ROOT, ("signal_lab",))

        git.assert_called_once_with(ROOT, "submodule", "update", "--init", "--recursive",
            "--", "apps/signal_lab")

    def test_dirty_candidate_requires_explicit_discard(self) -> None:
        dirty = AppBoundary("signal_lab", ROOT / "apps/signal_lab", "submodule", True, False)
        selected = AppBoundary("primary_app", ROOT / "apps/primary_app", "submodule", True, True)
        with patch("monotools.provisioning.repositories.app_boundary_inventory",
                return_value=(dirty, selected)):
            with self.assertRaisesRegex(RepositoryError, "uncommitted or unpinned"):
                focus_app_workspace(ROOT, "primary_app")


if __name__ == "__main__":
    unittest.main()
