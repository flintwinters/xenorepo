"""Kanban domain, HTTP, persistence, and build contracts."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
import unittest

import httpx

from apps.kanban.backend.database import Base, KanbanStore
from apps.kanban.backend.server import create_app
from monotools.orchestration.apps import ROOT, get_app
from monotools.orchestration.lifecycle import build_app
from monotools.persistence.database import create_session_factory


class Client:
    def __init__(self, application) -> None:
        self.application = application

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.application),
                base_url="http://kanban.test") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(send())


class ApplicationTests(unittest.TestCase):
    database = Path("apps/kanban/data/test-kanban.db")
    uploads = Path("apps/kanban/data/test-uploads")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.uploads.mkdir(parents=True, exist_ok=True)
        for path in self.uploads.iterdir():
            path.unlink()
        self.sessions = create_session_factory(f"sqlite:///{self.database}", Base.metadata)
        clock = lambda: datetime(2026, 8, 31, 14, 30, tzinfo=UTC)
        self.store = KanbanStore(self.sessions, now=clock)
        self.client = Client(create_app(store=self.store, uploads=self.uploads))

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)
        for path in self.uploads.iterdir():
            path.unlink()
        self.uploads.rmdir()

    def column(self, name: str = "Doing") -> dict:
        response = self.client.request("POST", "/api/columns", json={"name": name})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def card(self, column_id: str, title: str = "Write tests") -> dict:
        response = self.client.request("POST", "/api/cards", json={"column_id": column_id,
            "title": title, "description": "Prove persistence", "assignee": "Felix",
            "labels": ["Quality", "quality", "Backend"], "priority": "high"})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_board_column_card_ordering_and_restart_persist(self) -> None:
        board = self.client.request("PATCH", "/api/board",
            json={"name": "Ship it", "description": "One honest board"})
        first, second = self.column("Queue"), self.column("Doing")
        one, two = self.card(first["id"], "One"), self.card(first["id"], "Two")
        self.assertEqual(one["labels"], ["Quality", "Backend"])
        moved = self.client.request("PUT", f"/api/cards/{two['id']}/position",
            json={"column_id": second["id"], "position": 0})
        reordered = self.client.request("PUT", f"/api/columns/{second['id']}/position",
            json={"position": 0})
        self.assertEqual((board.status_code, moved.status_code, reordered.status_code), (200, 200, 200))
        restarted = Client(create_app(store=KanbanStore(self.sessions), uploads=self.uploads))
        view = restarted.request("GET", "/api/board").json()
        self.assertEqual(view["board"]["name"], "Ship it")
        self.assertEqual([value["name"] for value in view["columns"][:2]], ["Doing", "Queue"])
        persisted_move = next(value for value in view["cards"] if value["id"] == two["id"])
        self.assertEqual(persisted_move["column_id"], second["id"])
        self.assertGreaterEqual(len(view["activity"]), 7)

    def test_comments_links_uploads_edits_and_recoverable_archive(self) -> None:
        column, = [self.column()]
        card = self.card(column["id"])
        comment = self.client.request("POST", f"/api/cards/{card['id']}/comments",
            json={"body": "Initial note"}).json()
        edited = self.client.request("PATCH", f"/api/comments/{comment['id']}",
            json={"body": "Corrected note"})
        link = self.client.request("POST", f"/api/cards/{card['id']}/links",
            json={"title": "Reference", "url": "https://example.com/spec"}).json()
        upload = self.client.request("POST", f"/api/cards/{card['id']}/uploads",
            content=b"evidence", headers={"X-Attachment-Title": "Evidence",
                "X-File-Name": "proof.txt", "Content-Type": "text/plain"})
        self.assertEqual((edited.status_code, upload.status_code), (200, 201))
        uploaded = upload.json()
        content = self.client.request("GET", f"/api/attachments/{uploaded['id']}/content")
        self.assertEqual(content.content, b"evidence")
        self.assertEqual(self.client.request("DELETE",
            f"/api/archive/attachment/{link['id']}").status_code, 204)
        self.assertEqual(self.client.request("POST",
            f"/api/archive/attachment/{link['id']}/restore").status_code, 204)
        view = self.client.request("GET", "/api/board").json()
        self.assertEqual(view["comments"][0]["body"], "Corrected note")
        self.assertIsNone(next(value for value in view["attachments"]
            if value["id"] == link["id"])["archived_at"])

    def test_archive_parent_rules_validation_origin_and_activity_immutability(self) -> None:
        column, = [self.column()]
        card = self.card(column["id"])
        blocked = self.client.request("DELETE", f"/api/archive/column/{column['id']}")
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(self.client.request("DELETE",
            f"/api/archive/card/{card['id']}").status_code, 204)
        self.assertEqual(self.client.request("DELETE",
            f"/api/archive/column/{column['id']}").status_code, 204)
        restore_child = self.client.request("POST", f"/api/archive/card/{card['id']}/restore")
        self.assertEqual(restore_child.status_code, 409)
        forbidden = self.client.request("POST", "/api/columns",
            headers={"Origin": "https://foreign.test"}, json={"name": "Foreign"})
        invalid = self.client.request("POST", "/api/columns", json={"name": " "})
        activity_edit = self.client.request("PATCH", "/api/activity/missing", json={})
        self.assertEqual((forbidden.status_code, invalid.status_code, activity_edit.status_code),
            (403, 422, 404))

    def test_build_is_a_self_contained_typed_preact_document(self) -> None:
        definition = get_app("kanban")
        build_app(definition, ROOT)
        document = definition.document_for_route("/").read_text(encoding="utf-8")
        source = Path("apps/kanban/frontend/index.tsx").read_text(encoding="utf-8")
        client = Path("apps/kanban/frontend/client.ts").read_text(encoding="utf-8")
        self.assertIn("ARCHIVE", document)
        self.assertIn("/api/board", document)
        self.assertNotIn('src="', document)
        self.assertNotIn('rel="stylesheet"', document)
        self.assertIn('from "@xenorepo/ui";', source)
        self.assertIn('from "../data/openapi";', client)
        self.assertNotIn("window.alert", source)
        self.assertNotIn("window.confirm", source)
        self.assertNotIn("window.prompt", source)


if __name__ == "__main__":
    unittest.main()
