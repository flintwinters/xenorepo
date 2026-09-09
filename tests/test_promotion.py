"""Contracts for promoting a monolithic app into a GitHub submodule."""

from pathlib import Path
import unittest
from unittest.mock import patch

from monotools.orchestration.apps import ROOT
from monotools.provisioning.repositories import (
    AppRepositoryState, RepositoryError, promote_to_submodule,
)
import manage as repository_manager


class PromotionTests(unittest.TestCase):
    def test_promotion_requires_valid_github_identity(self) -> None:
        definition = repository_manager.MANAGERS[0][0]
        cases = (
            ("bad/owner", "app", "private", "owner"),
            ("owner", "bad/repo", "private", "repository"),
            ("owner", "app", "secret", "visibility"),
        )
        for owner, repository, visibility, message in cases:
            with self.subTest(owner=owner, repository=repository, visibility=visibility), \
                    self.assertRaisesRegex(RepositoryError, message):
                promote_to_submodule(definition, ROOT, owner=owner, repository=repository,
                    visibility=visibility, verify=lambda: None)

    def test_promotion_snapshots_verified_app_changes_before_export(self) -> None:
        definition = repository_manager.MANAGERS[0][0]
        split = "a" * 40
        calls: list[tuple[tuple[str, ...], Path]] = []

        def command(arguments: list[str], cwd: Path) -> str:
            calls.append((tuple(arguments), cwd))
            joined = " ".join(arguments)
            responses = {
                "ls-files --stage": "100644 b app.yaml",
                "status --short": f" M apps/{definition.name}/app.yaml",
                "diff --cached --name-only": "",
                "subtree split": split,
                "gh repo view": "git@github.com:owner/app.git",
            }
            if joined.endswith("rev-parse HEAD"):
                return split
            return next((value for key, value in responses.items() if key in joined), "")

        verified: list[str] = []
        state = AppRepositoryState("monolith", False, None, "current")
        with patch("monotools.provisioning.repositories.shutil.which", return_value="/usr/bin/tool"), \
             patch("monotools.provisioning.repositories.inspect_app_repository", return_value=state), \
             patch("monotools.provisioning.repositories._run", side_effect=command):
            remote = promote_to_submodule(definition, ROOT, owner="owner", repository="app",
                visibility="private", verify=lambda: verified.append("verified"))

        self.assertEqual(remote, "git@github.com:owner/app.git")
        self.assertEqual(verified, ["verified", "verified"])
        commands = [" ".join(arguments) for arguments, _ in calls]
        self.assertIn(f"git add -A -- apps/{definition.name}", commands)
        snapshot = next(i for i, item in enumerate(commands) if "git commit -m Prepare" in item)
        split_index = next(i for i, item in enumerate(commands) if "subtree split" in item)
        self.assertLess(snapshot, split_index)
        self.assertLess(split_index, next(i for i, item in enumerate(commands)
            if "gh repo create" in item))
        self.assertLess(next(i for i, item in enumerate(commands) if "git push" in item),
            next(i for i, item in enumerate(commands) if "git rm -r" in item))
        self.assertIn("git submodule add", "\n".join(commands))
        self.assertTrue(commands[-1].startswith("git commit -m"))


if __name__ == "__main__":
    unittest.main()
