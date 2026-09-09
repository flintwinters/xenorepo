"""Contracts for creating a focused Xenorepo derivative."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from monotools.orchestration.apps import ROOT
from monotools.provisioning.repositories import (
    AppRepositoryState, FocusedWorkspace, authenticated_github_owner, fork_focused_workspace,
)
import manage as repository_manager


class WorkspaceForkTests(unittest.TestCase):
    def test_authenticated_github_owner_uses_the_active_cli_account(self) -> None:
        with patch("monotools.provisioning.repositories.shutil.which", return_value="/usr/bin/gh"), \
             patch("monotools.provisioning.repositories._run", return_value="account") as run:
            owner = authenticated_github_owner(ROOT)

        self.assertEqual(owner, "account")
        run.assert_called_once_with(["gh", "api", "user", "--jq", ".login"], ROOT)

    def test_focused_workspace_is_detached_before_verification(self) -> None:
        source_definition = repository_manager.MANAGERS[0][0]
        events: list[str] = []
        with TemporaryDirectory(dir=ROOT / "tests", prefix="focused-parent-") as temporary:
            workspace = Path(temporary) / "source"
            app_directory = workspace / "apps" / source_definition.name
            app_directory.mkdir(parents=True)
            destination = Path(temporary) / "focused"
            definition = replace(source_definition, directory=app_directory)

            def git(_cwd: Path, *arguments: str) -> str:
                events.append("git " + " ".join(arguments))
                if arguments[0] == "clone":
                    destination.mkdir()
                responses = {
                    ("symbolic-ref", "--quiet", "--short", "HEAD"): "main",
                    ("ls-tree", "-d", "--name-only", "HEAD:apps"):
                        f"{definition.name}\nunrelated",
                    ("rev-parse", "--short", "HEAD"): "abc1234",
                }
                return responses.get(arguments, "")

            def verify(path: Path) -> None:
                self.assertEqual(path, destination)
                events.append("verify")

            state = AppRepositoryState("submodule", True,
                "git@github.com:owner/app.git", "current")
            with patch("monotools.provisioning.repositories.shutil.which",
                    return_value="/usr/bin/tool"), \
                 patch("monotools.provisioning.repositories.inspect_app_repository",
                    return_value=state), \
                 patch("monotools.provisioning.repositories._git", side_effect=git):
                focused = fork_focused_workspace(definition, workspace, destination=destination,
                    verify=verify)

        self.assertIsInstance(focused, FocusedWorkspace)
        self.assertEqual(focused.revision, "abc1234")
        self.assertIn("git rm -r -f -- apps/unrelated", events)
        self.assertNotIn(f"git rm -r -f -- apps/{definition.name}", events)
        self.assertIn("git remote remove origin", events)
        self.assertLess(events.index("git remote remove origin"), events.index("verify"))
        self.assertFalse(any(event.startswith("gh ") for event in events))


if __name__ == "__main__":
    unittest.main()
