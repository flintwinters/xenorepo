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
from monotools.runtime.monoform import monoform_manifest


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
            json={"name": "Ship it", "description": "One honest board", "default_priority": "urgent",
                "background_color": "#112233", "accent_color": "#44aa88",
                "label_colors": {"Quality": "#335577"}})
        first = self.client.request("POST", "/api/columns",
            json={"name": "Queue", "color": "#445566"}).json()
        second = self.column("Doing")
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
        self.assertEqual((view["board"]["default_priority"], view["board"]["background_color"],
            view["board"]["label_colors"]), ("urgent", "#112233", {"quality": "#335577"}))
        self.assertEqual(next(value for value in view["columns"]
            if value["id"] == first["id"])["color"], "#445566")
        self.assertEqual([value["name"] for value in view["columns"][:2]], ["Doing", "Queue"])
        persisted_move = next(value for value in view["cards"] if value["id"] == two["id"])
        self.assertEqual(persisted_move["column_id"], second["id"])
        self.assertGreaterEqual(len(view["activity"]), 7)

    def test_modal_crud_operations_are_declared_for_monoform(self) -> None:
        operations = monoform_manifest(self.client.application.openapi(), app="kanban",
            title="Kanban")["operations"]
        self.assertEqual({operation["operationId"] for operation in operations}, {
            "create_card", "create_column", "edit_attachment", "edit_board_details", "edit_card",
            "edit_column", "edit_comment", "set_label_color",
        })
        label_color = next(operation for operation in operations
            if operation["operationId"] == "set_label_color")
        self.assertEqual(label_color["bodySchema"]["properties"]["color"], {
            "format": "color", "pattern": "^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
            "title": "Label color", "type": "string",
        })
        original = self.client.request("PATCH", "/api/board", json={
            "name": "Original", "description": "Before", "default_priority": "normal",
            "background_color": "#112233", "accent_color": "#445566",
            "label_colors": {"Priority": "#778899"},
        })
        details = self.client.request("PATCH", "/api/board/details", json={
            "name": "Focused", "description": "After", "default_priority": "urgent",
        })
        color = self.client.request("PATCH", "/api/board/label-colors/Priority",
            json={"color": "#abc"})
        self.assertEqual((original.status_code, details.status_code, color.status_code), (200, 200, 200))
        self.assertEqual((color.json()["name"], color.json()["default_priority"]), ("Focused", "urgent"))
        self.assertEqual((color.json()["background_color"], color.json()["accent_color"],
            color.json()["label_colors"]), ("#112233", "#445566", {"priority": "#abc"}))

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

    def test_archiving_a_column_cascades_to_cards_and_preserves_parent_rules(self) -> None:
        column, = [self.column()]
        card = self.card(column["id"])
        self.assertEqual(self.client.request("DELETE",
            f"/api/archive/column/{column['id']}").status_code, 204)
        view = self.client.request("GET", "/api/board").json()
        archived_card = next(value for value in view["cards"] if value["id"] == card["id"])
        self.assertIsNotNone(archived_card["archived_at"])
        self.assertIn(f"Archived card “{card['title']}” with column “{column['name']}”",
            [item["summary"] for item in view["activity"]])
        restore_child = self.client.request("POST", f"/api/archive/card/{card['id']}/restore")
        self.assertEqual(restore_child.status_code, 409)
        self.assertEqual(self.client.request("POST",
            f"/api/archive/column/{column['id']}/restore").status_code, 204)
        self.assertEqual(self.client.request("POST",
            f"/api/archive/card/{card['id']}/restore").status_code, 204)
        forbidden = self.client.request("POST", "/api/columns",
            headers={"Origin": "https://foreign.test"}, json={"name": "Foreign"})
        invalid = self.client.request("POST", "/api/columns", json={"name": " "})
        activity_edit = self.client.request("PATCH", "/api/activity/missing", json={})
        self.assertEqual((forbidden.status_code, invalid.status_code, activity_edit.status_code),
            (403, 422, 404))

    def test_frontend_preserves_the_typed_board_contract(self) -> None:
        definition = get_app("kanban")
        build_app(definition, ROOT)
        document = definition.document_for_route("/").read_text(encoding="utf-8")
        source = Path("apps/kanban/frontend/index.tsx").read_text(encoding="utf-8")
        client = Path("apps/kanban/frontend/client.ts").read_text(encoding="utf-8")
        color = Path("apps/kanban/frontend/color.ts").read_text(encoding="utf-8")
        self.assertIn("ARCHIVE", document)
        self.assertIn("/api/board", document)
        for coefficient in ("0.2126", "0.7152", "0.0722"):
            self.assertIn(coefficient, color)
        self.assertIn('from "monoui";', source)
        self.assertIn("Modal", source)
        self.assertNotIn("<form onSubmit={this.save", source)
        self.assertIn('from "../data/openapi";', client)
        self.assertNotIn("window.alert", source)
        self.assertNotIn("window.confirm", source)
        self.assertNotIn("window.prompt", source)
        self.assertNotIn('type="color"', source)
        self.assertNotIn("<button", source)

    def test_append_and_replace_import_are_atomic_and_remap_relationships(self) -> None:
        existing = self.column("Existing")
        self.card(existing["id"], "Keep me")
        document = {
            "name": "Imported", "description": "Migration", "default_priority": "urgent",
            "background_color": "#112233", "accent_color": "#445566",
            "label_colors": {"Legacy": "#778899"},
            "columns": [{"id": "legacy-column", "name": "Legacy", "color": "#abcdef"}],
            "cards": [{"id": "legacy-card", "column_id": "legacy-column", "title": "Moved",
                "description": "Old work", "assignee": "Felix", "labels": ["Legacy"],
                "priority": "high", "color": "#123456"}],
            "comments": [{"card_id": "legacy-card", "body": "Old note"}],
            "attachments": [{"card_id": "legacy-card", "kind": "link", "title": "Source",
                "url": "https://example.com/legacy", "original_name": None, "media_type": None}],
        }
        appended = self.client.request("POST", "/api/import/append", json=document)
        self.assertEqual(appended.json(), {"mode": "append", "columns": 1, "cards": 1,
            "comments": 1, "attachments": 1})
        view = self.client.request("GET", "/api/board").json()
        self.assertEqual(view["board"]["name"], "My board")
        self.assertEqual([value["name"] for value in view["columns"]], ["Existing", "Legacy"])
        imported_column = next(value for value in view["columns"] if value["name"] == "Legacy")
        imported_card = next(value for value in view["cards"] if value["title"] == "Moved")
        self.assertNotEqual((imported_column["id"], imported_card["id"]),
            ("legacy-column", "legacy-card"))
        self.assertEqual(imported_card["column_id"], imported_column["id"])
        self.assertEqual(view["comments"][0]["card_id"], imported_card["id"])
        self.assertEqual(view["attachments"][0]["card_id"], imported_card["id"])

        invalid = {**document, "cards": [{**document["cards"][0], "column_id": "missing"}]}
        self.assertEqual(self.client.request("POST", "/api/import/replace", json=invalid).status_code, 422)
        self.assertEqual(len(self.client.request("GET", "/api/board").json()["columns"]), 2)
        self.assertEqual(self.client.request("POST", "/api/import/replace", json=document).status_code, 200)
        view = self.client.request("GET", "/api/board").json()
        self.assertEqual((view["board"]["name"], view["board"]["default_priority"],
            view["board"]["label_colors"]), ("Imported", "urgent", {"legacy": "#778899"}))
        self.assertEqual([value["name"] for value in view["columns"]], ["Legacy"])
        self.assertEqual([value["title"] for value in view["cards"]], ["Moved"])
        self.assertEqual(len(view["activity"]), 1)
        upload = {**document, "attachments": [{**document["attachments"][0],
            "kind": "upload", "url": None, "original_name": "lost.txt", "media_type": "text/plain"}]}
        self.assertEqual(self.client.request("POST", "/api/import/append", json=upload).status_code, 422)
        foreign = self.client.request("POST", "/api/import/append", json=document,
            headers={"Origin": "https://foreign.test"})
        self.assertEqual(foreign.status_code, 403)


if __name__ == "__main__":
    unittest.main()
