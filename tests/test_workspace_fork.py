"""Contracts for creating a focused Xenorepo derivative."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from monotools.orchestration.apps import ROOT
from monotools.provisioning.repositories import (
    AppRepositoryState, FocusedWorkspace, fork_focused_workspace,
)
import manage as repository_manager


class WorkspaceForkTests(unittest.TestCase):
    def test_focused_workspace_is_verified_before_remote_creation(self) -> None:
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

            def gh(_cwd: Path, *arguments: str) -> str:
                events.append("gh " + " ".join(arguments))
                return "git@github.com:owner/focused.git" if arguments[:2] == (
                    "repo", "view") else ""

            def verify(path: Path) -> None:
                self.assertEqual(path, destination)
                events.append("verify")

            state = AppRepositoryState("submodule", True,
                "git@github.com:owner/app.git", "current")
            with patch("monotools.provisioning.repositories.shutil.which",
                    return_value="/usr/bin/tool"), \
                 patch("monotools.provisioning.repositories.inspect_app_repository",
                    return_value=state), \
                 patch("monotools.provisioning.repositories._optional_remote",
                    return_value="git@github.com:owner/xenorepo.git"), \
                 patch("monotools.provisioning.repositories._git", side_effect=git), \
                 patch("monotools.provisioning.repositories._gh", side_effect=gh):
                focused = fork_focused_workspace(definition, workspace, destination=destination,
                    owner="owner", repository="focused", visibility="private", verify=verify)

        self.assertIsInstance(focused, FocusedWorkspace)
        self.assertEqual((focused.remote, focused.revision),
            ("git@github.com:owner/focused.git", "abc1234"))
        self.assertIn("git rm -r -f -- apps/unrelated", events)
        self.assertNotIn(f"git rm -r -f -- apps/{definition.name}", events)
        self.assertLess(events.index("verify"),
            events.index("gh repo create owner/focused --private --description "
                f"Focused Xenorepo workspace for {definition.title} --disable-wiki"))
        self.assertLess(events.index("verify"), events.index("git push -u origin main"))


if __name__ == "__main__":
    unittest.main()
