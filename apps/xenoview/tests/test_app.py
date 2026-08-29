"""Cockpit measurement, persistence, and HTTP contract tests."""

from datetime import UTC, datetime
from pathlib import Path
import asyncio
import unittest

import httpx

from apps.xenoview.backend.database import Base, SnapshotRepository
from apps.xenoview.backend.scanner import scan_architecture, scan_modules, scan_overview, scan_tree
from apps.xenoview.backend.server import ROOT, create_app
from monotools.database import create_session_factory


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
        self.assertEqual(set(overview["test_breakdown"]["monoapps"]),
            {path.parent.name for path in ROOT.glob("apps/*/app.yaml")})
        self.assertGreater(overview["test_breakdown"]["monorepo"], 0)
        self.assertIn("Python", {item["language"] for item in overview["language_lines"]})
        self.assertGreaterEqual(overview["specification"]["covered"], 1)
        self.assertLessEqual(overview["specification"]["covered"],
            overview["metrics"]["monoapps"])

    def test_modules_and_architecture_are_derived(self) -> None:
        modules = scan_modules(ROOT)
        architecture = scan_architecture(ROOT)
        self.assertEqual([item["name"] for item in modules], sorted(item["name"] for item in modules))
        self.assertIn("audit", {item["name"] for item in modules})
        edges = {(item["source"], item["target"]) for item in architecture["edges"]}
        self.assertIn(("app:xenoview", "monotools"), edges)
        self.assertIn(("app:xenoview", "storage"), edges)

    def test_tree_is_complete_and_excludes_dependencies_and_artifacts(self) -> None:
        tree = scan_tree(ROOT)
        self.assertEqual((tree["kind"], tree["name"]), ("directory", "xenorepo"))
        self.assertIn("ls_colors", tree)
        root_names = [item["name"] for item in tree["children"]]
        self.assertNotIn("node_modules", root_names)
        self.assertNotIn(".venv", root_names)
        apps = next(item for item in tree["children"] if item["name"] == "apps")
        xenoview = next(item for item in apps["children"] if item["name"] == "xenoview")
        self.assertNotIn("dist", {item["name"] for item in xenoview["children"]})

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

    def test_build_is_self_contained_modular_lit_client(self) -> None:
        document = Path("apps/xenoview/dist/index.html").read_text(encoding="utf-8")
        source = Path("apps/xenoview/frontend/index.ts").read_text(encoding="utf-8")
        self.assertIn("XENO // COCKPIT", document)
        self.assertIn("/api/overview", document)
        self.assertNotIn("APP_BUNDLE", document)
        self.assertIn('import { cockpitStyles } from "./styles.js";', source)


if __name__ == "__main__":
    unittest.main()
