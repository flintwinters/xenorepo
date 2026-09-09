"""Real Git proofs for local promotion and retryable focused workspace creation."""

from dataclasses import replace
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

import manage
from monotools.provisioning.repositories import (
    RepositoryError, fork_focused_workspace, promote_to_submodule,
)
from monotools.provisioning.scaffolding import scaffold_app


class RepositoryTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        data = manage.ROOT / "tests" / "data"
        data.mkdir(exist_ok=True)
        self.temporary = TemporaryDirectory(prefix="repository-", dir=data)
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.workspace = self.parent / "source"
        self.workspace.mkdir()
        self.git(self.workspace, "init", "-b", "main")
        self.git(self.workspace, "config", "user.name", "Repository Tests")
        self.git(self.workspace, "config", "user.email", "tests@example.invalid")
        self.environment = patch.dict("os.environ", {
            "GIT_AUTHOR_NAME": "Repository Tests", "GIT_AUTHOR_EMAIL": "tests@example.invalid",
            "GIT_COMMITTER_NAME": "Repository Tests",
            "GIT_COMMITTER_EMAIL": "tests@example.invalid",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        directory = scaffold_app(self.workspace / "apps", "fixture", "Fixture")
        (self.workspace / ".gitignore").write_text("/data/\n", encoding="utf-8")
        self.definition = replace(manage.MANAGERS[0][0], name="fixture",
            title="Fixture", directory=directory)
        self.git(self.workspace, "add", ".")
        self.git(self.workspace, "commit", "-m", "Create test workspace")
        self.backing = self.workspace / "data" / "repositories" / "fixture"
        self.destination = self.workspace / "data" / "workspaces" / "fixture"

    def git(self, directory: Path, *arguments: str) -> str:
        result = subprocess.run(["git", *arguments], cwd=directory, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout.strip()

    def promote(self) -> None:
        promote_to_submodule(self.definition, self.workspace,
            repository_directory=self.backing)

    def test_missing_original_repository_does_not_prevent_fork_or_refork(self) -> None:
        self.promote()
        self.backing.rename(self.parent / "moved-backing")
        fork_focused_workspace(self.definition, self.workspace, destination=self.destination)
        app = self.destination / "apps" / "fixture"
        self.assertEqual(self.git(app, "status", "--porcelain"), "")
        self.assertTrue((app / "README.md").is_file())
        self.assertEqual(self.git(self.destination, "remote"), "")
        fork_focused_workspace(replace(self.definition, directory=app), self.destination,
            destination=self.parent / "refocused")

    def test_clone_failure_leaves_no_destination_and_allows_retry(self) -> None:
        self.promote()
        revision = self.git(self.workspace, "rev-parse", "HEAD")
        populate = "monotools.provisioning.repositories._populate_focused_workspace"
        with patch(populate, side_effect=RepositoryError("injected clone failure")), \
             self.assertRaisesRegex(RepositoryError, "no workspace was created"):
            fork_focused_workspace(self.definition, self.workspace, destination=self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.destination.parent.glob("fixture-pending-*")), [])
        self.assertEqual(self.git(self.workspace, "rev-parse", "HEAD"), revision)
        fork_focused_workspace(self.definition, self.workspace, destination=self.destination)
        self.assertTrue(self.destination.is_dir())

    def test_existing_destination_is_rejected_before_promotion(self) -> None:
        self.destination.mkdir(parents=True)
        with patch("manage.MANAGERS", ((self.definition, None),)), \
             patch("manage.ROOT", self.workspace), patch("manage._promote_before_forking") as promote:
            result = CliRunner().invoke(manage.app, ["monoapp", "fork-workspace", "fixture",
                "--directory", str(self.destination)])
        self.assertEqual(result.exit_code, 1, result.output)
        promote.assert_not_called()
        self.assertFalse(self.backing.exists())

    def test_clone_failure_does_not_claim_the_destination(self) -> None:
        self.promote()
        with patch("monotools.provisioning.repositories._populate_focused_workspace",
                side_effect=RepositoryError("injected clone failure")), \
             self.assertRaisesRegex(RepositoryError, "injected clone failure"):
            fork_focused_workspace(self.definition, self.workspace,
                destination=self.destination)
        self.assertFalse(self.destination.exists())
        fork_focused_workspace(self.definition, self.workspace, destination=self.destination)
        self.assertEqual(self.git(self.destination / "apps/fixture", "status", "--porcelain"), "")
