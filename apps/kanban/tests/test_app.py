"""Kanban domain and HTTP vertical-slice tests."""

from pathlib import Path
import asyncio
import unittest

import httpx
from sqlalchemy import select

from apps.kanban.database import (
    BoardStore, CardCreate, CardRecord, CardUpdate, Mutation, MutationCard,
    create_session_factory,
)
from apps.kanban.server import create_app


class AppClient:
    """Small synchronous facade over HTTPX's in-process ASGI transport."""

    def __init__(self, application) -> None:
        self.application = application

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.application)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://kanban.test"
            ) as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)


class KanbanTests(unittest.TestCase):
    database = Path("apps/kanban/data/test-kanban.db")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.sessions = create_session_factory(f"sqlite:///{self.database}")
        self.store = BoardStore(self.sessions)
        self.client = AppClient(create_app(store=self.store))

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    def create(self, title: str, column: str = "todo") -> dict[str, str]:
        response = self.client.post("/api/cards", json={"title": title, "column_id": column})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_http_card_lifecycle_and_validation(self) -> None:
        initial = self.client.get("/api/board").json()
        self.assertEqual([column["id"] for column in initial["columns"]],
            ["todo", "doing", "done"])
        self.assertEqual(initial["cards"], [])
        card = self.create("  Verify the slice  ")
        self.assertEqual(card["title"], "Verify the slice")
        moved = self.client.patch(f"/api/cards/{card['id']}", json={"column_id": "done"})
        self.assertEqual((moved.status_code, moved.json()["column_id"]), (200, "done"))
        self.assertEqual(self.client.delete(f"/api/cards/{card['id']}").status_code, 204)
        self.assertEqual(self.client.get("/api/board").json()["cards"], [])
        self.assertEqual(self.client.post("/api/cards",
            json={"title": " ", "column_id": "todo"}).status_code, 422)
        unknown = self.client.post("/api/cards",
            json={"title": "Lost", "column_id": "missing"})
        self.assertEqual((unknown.status_code, unknown.json()),
            (422, {"error": "Unknown column: missing"}))
        self.assertEqual(self.client.patch("/api/cards/missing",
            json={"column_id": "done"}).status_code, 404)
        forbidden = self.client.post("/api/cards", headers={"Origin": "https://foreign.test"},
            json={"title": "Cross origin", "column_id": "todo"})
        self.assertEqual((forbidden.status_code, forbidden.json()),
            (403, {"error": "Request origin is not allowed."}))

    def test_history_reverses_mutations_and_discards_abandoned_redo(self) -> None:
        first = self.create("First")
        second = self.create("Second", "doing")
        self.client.patch(f"/api/cards/{first['id']}", json={"column_id": "done"})
        self.client.delete(f"/api/cards/{second['id']}")
        restored = self.client.post("/api/undo").json()
        self.assertEqual([card["id"] for card in restored["cards"]],
            [second["id"], first["id"]])
        self.client.post("/api/undo")
        replacement = self.create("Replacement")
        self.assertEqual(self.client.post("/api/redo").status_code, 409)
        ids = [card["id"] for card in self.client.get("/api/board").json()["cards"]]
        self.assertEqual(ids, [first["id"], replacement["id"], second["id"]])

    def test_rename_and_precise_ordering_are_reversible(self) -> None:
        first = self.create("First")
        second = self.create("Second")
        third = self.create("Third", "doing")
        renamed = self.client.patch(f"/api/cards/{first['id']}", json={"title": "Alpha"})
        self.assertEqual(renamed.json()["title"], "Alpha")
        self.assertEqual(self.client.get("/api/board").json()["undo_description"],
            'Rename “First” to “Alpha”')
        self.client.patch(f"/api/cards/{second['id']}",
            json={"column_id": "todo", "index": 0})
        self.client.patch(f"/api/cards/{third['id']}",
            json={"column_id": "todo", "index": 1})
        titles = [card["title"] for card in self.client.get("/api/board").json()["cards"]]
        self.assertEqual(titles, ["Second", "Third", "Alpha"])
        undone = self.client.post("/api/undo").json()
        self.assertEqual([card["title"] for card in undone["cards"]],
            ["Second", "Alpha", "Third"])
        redone = self.client.post("/api/redo").json()
        self.assertEqual([card["title"] for card in redone["cards"]],
            ["Second", "Third", "Alpha"])
        self.assertEqual(self.client.patch(f"/api/cards/{first['id']}",
            json={"index": 4}).status_code, 422)

    def test_state_and_normalized_history_survive_restart(self) -> None:
        created = self.store.create(CardCreate(title="Durable", column_id="todo"))
        self.store.update(created.id, CardUpdate(column_id="done"))
        restarted = BoardStore(self.sessions)
        self.assertEqual(restarted.snapshot().cards,
            [created.model_copy(update={"column_id": "done"})])
        self.assertEqual(restarted.undo().cards, [created])
        with self.sessions() as session:
            self.assertGreater(len(session.scalars(select(Mutation)).all()), 0)
            snapshots = session.scalars(select(MutationCard)).all()
            self.assertTrue(snapshots)
            self.assertTrue(all(row.phase in {"before", "after"} for row in snapshots))
            self.assertEqual(session.scalars(select(CardRecord.position)).all(), [0])

    def test_history_descriptions_have_a_legacy_fallback(self) -> None:
        self.create("Legacy")
        with self.sessions.begin() as session:
            session.scalar(select(Mutation)).description = None
        self.assertEqual(self.store.snapshot().undo_description, "Update board")
        self.assertEqual(self.store.undo().cards, [])
        self.assertEqual(self.store.snapshot().redo_description, "Update board")

    def test_build_is_a_self_contained_client(self) -> None:
        document = Path("apps/kanban/dist/index.html").read_text(encoding="utf-8")
        self.assertIn("KANBAN // 01", document)
        self.assertIn("/api/board", document)
        self.assertNotIn("APP_BUNDLE", document)


if __name__ == "__main__":
    unittest.main()
