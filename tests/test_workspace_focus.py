"""Contracts for focusing the current Xenorepo on one in-place monoapp workspace."""

import unittest
from unittest.mock import patch

import typer
from typer.testing import CliRunner

import manage
from monotools.orchestration.apps import ROOT
from monotools.provisioning.repositories import AppRepositoryState


class WorkspaceFocusTests(unittest.TestCase):
    def test_command_offers_focus_then_promotion_and_reports_app_worktree(self) -> None:
        selected = manage.MANAGERS[0][0]
        state = AppRepositoryState("monolith", True, None, "current")
        mutations = []
        with patch("manage.inspect_app_repository", return_value=state), \
             patch("manage._promote_monoapp", side_effect=lambda *_args, **_kwargs:
                mutations.append("promote")) as promote, \
             patch("manage.protect_upstream_remote",
                return_value="git@github.com:flintwinters/xenorepo.git") as protect, \
             patch("manage._offer_workspace_focus", side_effect=lambda *_:
                mutations.append("focus")) as focus:
            result = CliRunner().invoke(manage.app,
                ["monoapp", "fork-workspace", selected.name], input="y\n")

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("not promoted. Promote it for direct work", result.output)
        focus.assert_called_once_with(selected)
        protect.assert_called_once_with(ROOT)
        promote.assert_called_once_with(selected,
            repository_directory=ROOT / "data" / "repositories" / selected.name)
        self.assertEqual(mutations, ["focus", "promote"])
        self.assertIn(f"Working tree: {selected.directory}", result.output)
        self.assertIn("Source remote: upstream", result.output)

    def test_declined_promotion_causes_no_workspace_mutation(self) -> None:
        selected = manage.MANAGERS[0][0]
        state = AppRepositoryState("monolith", True, None, "current")
        with patch("manage.inspect_app_repository", return_value=state), \
             patch("manage._offer_workspace_focus") as focus, \
             patch("manage.protect_upstream_remote") as protect, \
             patch("manage._promote_monoapp") as promote:
            result = CliRunner().invoke(manage.app,
                ["monoapp", "fork-workspace", selected.name], input="n\n")

        self.assertEqual(result.exit_code, 1, result.output)
        focus.assert_not_called()
        protect.assert_not_called()
        promote.assert_not_called()

    def test_focus_requires_every_other_app_to_be_clean_before_removal(self) -> None:
        selected, other = (definition for definition, _ in manage.MANAGERS[:2])
        dirty = AppRepositoryState("monolith", False, None, "current")
        with patch("manage.MANAGERS", ((selected, None), (other, None))), \
             patch("manage.typer.confirm", return_value=True) as confirm, \
             patch("manage.inspect_app_repository", return_value=dirty), \
             patch("manage.delete_app") as delete, self.assertRaises(typer.Exit):
            manage._offer_workspace_focus(selected)

        confirm.assert_called_once()
        delete.assert_not_called()

    def test_focus_removes_every_other_clean_app(self) -> None:
        selected, *others = (definition for definition, _ in manage.MANAGERS[:3])
        clean = AppRepositoryState("monolith", True, None, "current")
        managers = tuple((definition, None) for definition in (selected, *others))
        with patch("manage.MANAGERS", managers), \
             patch("manage.typer.confirm", return_value=True), \
             patch("manage.inspect_app_repository", return_value=clean), \
             patch("manage.delete_app") as delete:
            manage._offer_workspace_focus(selected)

        self.assertEqual([call.args for call in delete.call_args_list],
            [(ROOT, definition.name) for definition in others])


if __name__ == "__main__":
    unittest.main()
