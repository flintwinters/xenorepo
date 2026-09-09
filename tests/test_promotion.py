"""Contracts for promoting a monolithic app into a local Git submodule."""

from pathlib import Path
from subprocess import CompletedProcess
import unittest
from unittest.mock import patch

from monotools.orchestration.apps import ROOT
from monotools.provisioning.repositories import (
    AppRepositoryState, promote_to_submodule,
)
import manage as repository_manager


class PromotionTests(unittest.TestCase):
    def test_promotion_restores_once_before_both_verification_passes(self) -> None:
        definition = repository_manager.MANAGERS[0][0]

        def promote(*_arguments, verify, **_options):
            verify()
            verify()
            return ROOT.parent / "app"

        with patch("manage.promote_to_submodule", side_effect=promote), \
             patch("manage.subprocess.run", return_value=CompletedProcess([], 0)) as run:
            repository_manager._promote_monoapp(definition,
                repository_directory=ROOT.parent / "app", aesthetic_review=False)

        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands.count(
            ["uv", "run", "manage.py", "restore", "--no-submodules"]), 1)
        self.assertEqual(commands.count(
            ["uv", "run", "manage.py", definition.name, "check"]), 2)

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
            }
            if joined.endswith("rev-parse HEAD"):
                return split
            return next((value for key, value in responses.items() if key in joined), "")

        verified: list[str] = []
        state = AppRepositoryState("monolith", False, None, "current")
        repository = ROOT.parent / "promotion-test-repository"
        with patch("monotools.provisioning.repositories.shutil.which", return_value="/usr/bin/tool"), \
             patch("monotools.provisioning.repositories.inspect_app_repository", return_value=state), \
             patch("monotools.provisioning.repositories._run", side_effect=command), \
             patch("pathlib.Path.mkdir"):
            promoted = promote_to_submodule(definition, ROOT,
                repository_directory=repository, verify=lambda: verified.append("verified"))

        self.assertEqual(promoted, repository)
        self.assertEqual(verified, ["verified", "verified"])
        commands = [" ".join(arguments) for arguments, _ in calls]
        self.assertIn(f"git add -A -- apps/{definition.name}", commands)
        snapshot = next(i for i, item in enumerate(commands) if "git commit -m Prepare" in item)
        split_index = next(i for i, item in enumerate(commands) if "subtree split" in item)
        self.assertLess(snapshot, split_index)
        self.assertLess(split_index, next(i for i, item in enumerate(commands)
            if "git init --initial-branch=main" in item))
        self.assertFalse(any(item.startswith("gh ") or "git push" in item for item in commands))
        self.assertIn("git submodule add", "\n".join(commands))
        self.assertTrue(commands[-1].startswith("git commit -m"))


if __name__ == "__main__":
    unittest.main()
