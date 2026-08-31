"""Kanban domain, HTTP, persistence, and build contract tests."""

from datetime import UTC, datetime
from pathlib import Path
import asyncio
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


class KanbanTests(unittest.TestCase):
    database = Path("apps/kanban/data/test-kanban.db")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.sessions = create_session_factory(f"sqlite:///{self.database}", Base.metadata)
        clock = lambda: datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
        self.store = KanbanStore(self.sessions, now=clock)
        self.client = Client(create_app(store=self.store))

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    def board(self) -> dict:
        response = self.client.request("GET", "/api/board")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def create_card(self, column_id: str, title: str) -> dict:
        response = self.client.request("POST", "/api/cards",
            json={"column_id": column_id, "title": title, "description": ""})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_seed_column_crud_ordering_and_protected_deletion(self) -> None:
        columns = self.board()["columns"]
        self.assertEqual([item["name"] for item in columns], ["Backlog", "In Progress", "Done"])
        added = self.client.request("POST", "/api/columns", json={"name": "Review"}).json()
        moved = self.client.request("PATCH", f"/api/columns/{added['id']}",
            json={"name": "Verify", "position": 1})
        self.assertEqual(moved.status_code, 200)
        self.assertEqual([item["name"] for item in moved.json()["columns"]],
            ["Backlog", "Verify", "In Progress", "Done"])
        card = self.create_card(added["id"], "Protect this work")
        self.assertEqual(self.client.request("DELETE",
            f"/api/columns/{added['id']}").status_code, 409)
        self.assertEqual(self.client.request("DELETE", f"/api/cards/{card['id']}").status_code, 204)
        self.assertEqual(self.client.request("DELETE",
            f"/api/columns/{added['id']}").status_code, 204)

    def test_card_edit_reorder_cross_column_move_and_restart(self) -> None:
        columns = self.board()["columns"]
        first, second = columns[0]["id"], columns[1]["id"]
        alpha = self.create_card(first, "Alpha")
        beta = self.create_card(first, "Beta")
        edited = self.client.request("PATCH", f"/api/cards/{beta['id']}",
            json={"title": "Beta edited", "description": "Durable detail"})
        self.assertEqual(edited.status_code, 200)
        reordered = self.client.request("PATCH", f"/api/cards/{beta['id']}",
            json={"column_id": first, "position": 0}).json()
        self.assertEqual([card["title"] for card in reordered["columns"][0]["cards"]],
            ["Beta edited", "Alpha"])
        moved = self.client.request("PATCH", f"/api/cards/{alpha['id']}",
            json={"column_id": second, "position": 0})
        self.assertEqual(moved.status_code, 200)
        restarted = Client(create_app(store=KanbanStore(self.sessions)))
        persisted = restarted.request("GET", "/api/board").json()["columns"]
        self.assertEqual(persisted[0]["cards"][0]["description"], "Durable detail")
        self.assertEqual(persisted[1]["cards"][0]["id"], alpha["id"])

    def test_invalid_positions_missing_ids_and_foreign_origins_fail(self) -> None:
        first = self.board()["columns"][0]["id"]
        card = self.create_card(first, "Known")
        cases = (
            self.client.request("POST", "/api/cards",
                json={"column_id": first, "title": " ", "description": ""}),
            self.client.request("PATCH", f"/api/cards/{card['id']}",
                json={"column_id": first}),
            self.client.request("PATCH", f"/api/cards/{card['id']}",
                json={"column_id": first, "position": 9}),
            self.client.request("PATCH", "/api/cards/missing", json={"title": "No"}),
            self.client.request("PATCH", "/api/columns/missing", json={"name": "No"}),
            self.client.request("POST", "/api/columns",
                headers={"Origin": "https://foreign.test"}, json={"name": "No"}),
        )
        self.assertEqual([response.status_code for response in cases], [422, 422, 422, 404, 404, 403])
        self.assertEqual([item["title"] for item in self.board()["columns"][0]["cards"]], ["Known"])

    def test_last_column_cannot_be_deleted(self) -> None:
        for column in self.board()["columns"][1:]:
            self.assertEqual(self.client.request("DELETE",
                f"/api/columns/{column['id']}").status_code, 204)
        remaining = self.board()["columns"][0]
        self.assertEqual(self.client.request("DELETE",
            f"/api/columns/{remaining['id']}").status_code, 409)

    def test_build_is_a_self_contained_typed_preact_client(self) -> None:
        definition = get_app("kanban")
        build_app(definition, ROOT)
        document = definition.document_for_route("/").read_text(encoding="utf-8")
        self.assertIn("Kanban Board", document)
        self.assertNotIn('src="', document)
        self.assertNotIn('rel="stylesheet"', document)


if __name__ == "__main__":
    unittest.main()
