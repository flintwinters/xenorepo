"""Real Git proofs for in-place local monoapp promotion."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from git import Repo

import manage
from monotools.provisioning.repositories import (
    UPSTREAM_PUSH_DISABLED_URL, inspect_app_repository, promote_to_submodule,
    protect_upstream_remote,
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

    def git(self, directory: Path, *arguments: str) -> str:
        if arguments[:1] == ("init",):
            Repo.init(directory, initial_branch="main")
            return ""
        return Repo(directory).git.execute(["git", *arguments]).strip()

    def promote(self) -> None:
        promote_to_submodule(self.definition, self.workspace,
            repository_directory=self.backing)

    def test_promotion_keeps_the_app_worktree_in_apps(self) -> None:
        self.promote()
        state = inspect_app_repository(self.definition, self.workspace)

        self.assertEqual(state.mode, "submodule")
        self.assertEqual(self.definition.directory, self.workspace / "apps" / "fixture")
        self.assertTrue((self.definition.directory / ".git").is_file())
        self.assertTrue(self.backing.is_dir())
        self.assertEqual(self.git(self.definition.directory, "status", "--porcelain"), "")

    def test_source_remote_is_fetchable_as_upstream_but_cannot_be_pushed(self) -> None:
        source = "git@github.com:flintwinters/xenorepo.git"
        self.git(self.workspace, "remote", "add", "origin", source)

        self.assertEqual(protect_upstream_remote(self.workspace), source)

        self.assertEqual(self.git(self.workspace, "remote", "get-url", "upstream"), source)
        self.assertEqual(self.git(self.workspace, "remote", "get-url", "--push", "upstream"),
            UPSTREAM_PUSH_DISABLED_URL)
        self.assertNotIn("origin", self.git(self.workspace, "remote").splitlines())

    def test_protecting_upstream_preserves_a_later_fork_origin(self) -> None:
        source = "git@github.com:flintwinters/xenorepo.git"
        fork = "git@github.com:owner/helpie-xenorepo.git"
        self.git(self.workspace, "remote", "add", "upstream", source)
        self.git(self.workspace, "remote", "add", "origin", fork)

        self.assertEqual(protect_upstream_remote(self.workspace), source)

        self.assertEqual(self.git(self.workspace, "remote", "get-url", "origin"), fork)
        self.assertEqual(self.git(self.workspace, "remote", "get-url", "--push", "upstream"),
            UPSTREAM_PUSH_DISABLED_URL)
