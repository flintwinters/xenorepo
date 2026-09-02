"""Cockpit measurement, persistence, and HTTP contract tests."""

from datetime import UTC, datetime
from pathlib import Path
import asyncio
import unittest
from unittest.mock import Mock

import httpx

from apps.xenoview.backend.database import Base, SnapshotRepository
from apps.xenoview.backend.scanner import (
    scan_history, scan_modules, scan_overview, scan_tree,
)
from apps.xenoview.backend.server import ROOT, create_app
from monotools.persistence.database import create_session_factory
from monotools.orchestration.services import ServiceError, ServiceStatus


class Client:
    def __init__(self, application) -> None:
        self.application = application

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.application),
                base_url="http://cockpit.test") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(send())


class CockpitTests(unittest.TestCase):
    database = Path("apps/xenoview/data/test-xenoview.db")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.sessions = create_session_factory(f"sqlite:///{self.database}", Base.metadata)
        clock = lambda: datetime(2026, 8, 28, 15, 0, tzinfo=UTC)
        self.repository = SnapshotRepository(self.sessions, clock=clock)
        self.client = Client(create_app(repository=self.repository))

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    def test_scorecard_and_test_breakdown_are_derived(self) -> None:
        overview = scan_overview(ROOT)
        self.assertGreater(overview["metrics"]["source_lines"], 1000)
        self.assertEqual(overview["metrics"]["test_cases"],
            overview["test_breakdown"]["total"])
        self.assertGreater(overview["metrics"]["test_files"], 0)
        self.assertEqual(set(overview["test_breakdown"]["monoapps"]),
            {path.parent.name for path in ROOT.glob("apps/*/app.yaml")})
        self.assertGreater(overview["test_breakdown"]["monorepo"], 0)
        self.assertIn("Python", {item["language"] for item in overview["language_lines"]})
        self.assertNotIn("JavaScript",
            {item["language"] for item in overview["language_lines"]})
        self.assertTrue(all(item["path"].startswith("apps/") and
            "/tests/" not in item["path"] for item in overview["largest_files"]))
        self.assertGreaterEqual(overview["specification"]["covered"], 1)
        self.assertLessEqual(overview["specification"]["covered"],
            overview["metrics"]["monoapps"])

    def test_modules_are_derived(self) -> None:
        modules = scan_modules(ROOT)
        self.assertEqual([item["name"] for item in modules], sorted(item["name"] for item in modules))
        names = {item["name"] for item in modules}
        self.assertTrue({"integrations.mailer", "orchestration.apps",
            "persistence.database", "runtime.application"}.issubset(names))
        self.assertTrue(all(item["description"] and item["explanation"] for item in modules))

    def test_modules_name_their_exact_app_consumers(self) -> None:
        appkit = next(item for item in scan_modules(ROOT) if item["name"] == "runtime.appkit")
        self.assertIn("xenoview", appkit["used_by_apps"])
        self.assertEqual(appkit["inbound_apps"], len(appkit["used_by_apps"]))

    def test_git_history_is_automatic_and_grouped_by_app_and_language(self) -> None:
        history = scan_history(ROOT, limit=12)
        self.assertTrue(history["available"])
        self.assertLessEqual(len(history["commits"]), 12)
        self.assertTrue(history["commits"])
        for commit in history["commits"]:
            self.assertEqual(commit["additions"], sum(item["added"] for item in commit["apps"]))
            self.assertEqual(commit["deletions"], sum(item["deleted"] for item in commit["apps"]))
            self.assertEqual([item["name"] for item in commit["apps"]],
                sorted(item["name"] for item in commit["apps"]))
        changed_languages = {item["name"] for commit in history["commits"]
            for item in commit["languages"]}
        self.assertTrue(changed_languages)

    def test_app_line_history_covers_root_apps_and_submodules(self) -> None:
        series = scan_history(ROOT, limit=12)["app_lines"]
        self.assertTrue(series)
        self.assertTrue(all(0 < len(item["points"]) <= 12 for item in series))
        self.assertTrue(all(point["lines"] >= 0 for item in series for point in item["points"]))
        names = [item["name"] for item in series]
        self.assertEqual(names, sorted(names))
        current_apps = {path.parent.name for path in ROOT.glob("apps/*/app.yaml")}
        self.assertTrue(current_apps.issubset(names))

    def test_tree_is_complete_and_excludes_dependencies_and_artifacts(self) -> None:
        tree = scan_tree(ROOT)
        self.assertEqual((tree["kind"], tree["name"]), ("directory", "xenorepo"))
        self.assertIn("ls_colors", tree)
        root_names = [item["name"] for item in tree["children"]]
        self.assertNotIn("node_modules", root_names)
        self.assertNotIn(".venv", root_names)
        self.assertNotIn(".state", root_names)
        self.assertNotIn("package-lock.json", root_names)
        apps = next(item for item in tree["children"] if item["name"] == "apps")
        xenoview = next(item for item in apps["children"] if item["name"] == "xenoview")
        self.assertNotIn("dist", {item["name"] for item in xenoview["children"]})
        for directory in (tree, apps, xenoview):
            expected = sorted(directory["children"],
                key=lambda item: (-item["lines"], item["name"]))
            self.assertEqual(directory["children"], expected)

    def test_snapshot_is_idempotent_schema_versioned_and_restart_durable(self) -> None:
        first = self.client.request("POST", "/api/snapshots").json()
        second = self.client.request("POST", "/api/snapshots").json()
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["snapshot"]["schema_version"], 1)
        restarted = Client(create_app(repository=SnapshotRepository(self.sessions)))
        history = restarted.request("GET", "/api/history").json()
        self.assertEqual((len(history), history[0]["fingerprint"]),
            (1, first["snapshot"]["fingerprint"]))

    def test_mutation_rejects_foreign_browser_origin(self) -> None:
        response = self.client.request("POST", "/api/snapshots",
            headers={"Origin": "https://foreign.test"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.request("GET", "/api/history").json(), [])

    def test_monoapp_status_and_lifecycle_routes_delegate_to_supervisor(self) -> None:
        stopped = ServiceStatus("calculator", "Calculator", 8100,
            "http://127.0.0.1:8100", False, False, False)
        running = ServiceStatus("calculator", "Calculator", 8100,
            "http://127.0.0.1:8100", True, True, True)
        supervisor = Mock()
        supervisor.statuses.return_value = [stopped]
        supervisor.start.return_value = running
        supervisor.stop.return_value = stopped
        client = Client(create_app(repository=self.repository, supervisor=supervisor))
        self.assertEqual(client.request("GET", "/api/monoapps").json()[0]["name"], "calculator")
        self.assertTrue(client.request("POST", "/api/monoapps/calculator/start").json()["running"])
        self.assertFalse(client.request("POST", "/api/monoapps/calculator/stop").json()["running"])
        supervisor.start.assert_called_once_with("calculator")
        supervisor.stop.assert_called_once_with("calculator")

    def test_monoapp_transitions_reject_foreign_origins_and_conflicts(self) -> None:
        supervisor = Mock()
        supervisor.start.side_effect = ServiceError("calculator is already running")
        client = Client(create_app(repository=self.repository, supervisor=supervisor))
        forbidden = client.request("POST", "/api/monoapps/calculator/start",
            headers={"Origin": "https://foreign.test"})
        conflict = client.request("POST", "/api/monoapps/calculator/start")
        self.assertEqual((forbidden.status_code, conflict.status_code), (403, 409))

    def test_openapi_describes_every_cockpit_response(self) -> None:
        schemas = create_app(repository=self.repository).openapi()["components"]["schemas"]
        self.assertTrue({"Overview", "ModuleFact", "TreeNode", "MonoappStatus",
            "SnapshotView", "SnapshotResult", "RepositoryHistory", "CommitFact"}.issubset(schemas))
        overview = schemas["Overview"]
        self.assertEqual(overview["additionalProperties"], False)
        self.assertIn("test_breakdown", overview["required"])

    def test_build_is_self_contained_typed_preact_client(self) -> None:
        document = Path("apps/xenoview/dist/index.html").read_text(encoding="utf-8")
        source = Path("apps/xenoview/frontend/index.tsx").read_text(encoding="utf-8")
        client = Path("apps/xenoview/frontend/client.ts").read_text(encoding="utf-8")
        self.assertIn("XENO // COCKPIT", document)
        self.assertIn("/api/overview", document)
        self.assertIn("/api/monoapps", document)
        self.assertNotIn("APP_BUNDLE", document)
        self.assertIn('from "monoui";', source)
        self.assertIn('from "../data/openapi";', client)
        self.assertNotIn("from \"lit\"", source)


if __name__ == "__main__":
    unittest.main()
