"""Contracts for promoting a monolithic app into a local Git submodule."""

from pathlib import Path
from subprocess import CompletedProcess
import unittest
from unittest.mock import patch

from monotools.orchestration.apps import ROOT
from monotools.provisioning.repositories import (
    AppRepositoryState, RepositoryError, promote_to_submodule,
)
import manage as repository_manager


class PromotionTests(unittest.TestCase):
    def test_promotion_does_not_restore_dependencies_or_run_product_checks(self) -> None:
        definition = repository_manager.MANAGERS[0][0]

        def promote(*_arguments, **_options):
            return ROOT.parent / "app"

        with patch("manage.promote_to_submodule", side_effect=promote), \
             patch("manage.subprocess.run", return_value=CompletedProcess([], 0)) as run:
            repository_manager._promote_monoapp(definition,
                repository_directory=ROOT.parent / "app")

        run.assert_not_called()

    def test_promotion_snapshots_current_app_changes_before_export(self) -> None:
        definition = repository_manager.MANAGERS[0][0]
        split = "a" * 40
        calls: list[tuple[tuple[str, ...], Path]] = []

        def command(cwd: Path, *arguments: str) -> str:
            calls.append((arguments, cwd))
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

        state = AppRepositoryState("monolith", False, None, "current")
        repository = ROOT.parent / "promotion-test-repository"
        with patch("monotools.provisioning.repositories.inspect_app_repository", return_value=state), \
             patch("monotools.provisioning.repositories._git", side_effect=command), \
             patch("pathlib.Path.mkdir"), \
             patch("monotools.provisioning.repositories.shutil.rmtree"):
            promoted = promote_to_submodule(definition, ROOT,
                repository_directory=repository)

        self.assertEqual(promoted, repository)
        commands = [" ".join(arguments) for arguments, _ in calls]
        self.assertIn(f"add -A -- apps/{definition.name}", commands)
        snapshot = next(i for i, item in enumerate(commands) if "commit -m Prepare" in item)
        split_index = next(i for i, item in enumerate(commands) if "subtree split" in item)
        self.assertLess(snapshot, split_index)
        self.assertLess(split_index, next(i for i, item in enumerate(commands)
            if "init --initial-branch=main" in item))
        self.assertFalse(any(item.startswith("gh ") or "push" in item for item in commands))
        self.assertIn("submodule add", "\n".join(commands))
        self.assertTrue(commands[-1].startswith("commit -m"))

    def test_failed_mount_rolls_back_to_the_committed_monolith(self) -> None:
        definition = repository_manager.MANAGERS[0][0]
        repository = ROOT.parent / "promotion-test-repository"
        with patch("monotools.provisioning.repositories._preflight",
                return_value=Path("apps") / definition.name), \
             patch("monotools.provisioning.repositories._commit_pending_app_changes"), \
             patch("monotools.provisioning.repositories._git", return_value="a" * 40), \
             patch("monotools.provisioning.repositories._create_local_repository"), \
             patch("monotools.provisioning.repositories._mount_local_repository",
                side_effect=RepositoryError("mount failed")), \
             patch("monotools.provisioning.repositories._restore_monolith") as restore, \
             self.assertRaisesRegex(RepositoryError, "rolled back after failure"):
            promote_to_submodule(definition, ROOT, repository_directory=repository)

        restore.assert_called_once()


if __name__ == "__main__":
    unittest.main()
