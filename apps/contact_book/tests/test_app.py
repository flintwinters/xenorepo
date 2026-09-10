"""Contact Book domain, HTTP, seed, and frontend contract tests."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
import unittest

import httpx

from apps.contact_book.backend.database import Base, ContactCreate, ContactStore
from apps.contact_book.backend.seeding import generated_contact, seed_contacts
from apps.contact_book.backend.server import create_app
from monotools.persistence.database import create_session_factory


class Client:
    def __init__(self, application) -> None:
        self.application = application

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.application),
                base_url="http://contacts.test") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(send())


class ContactBookTests(unittest.TestCase):
    database = Path("apps/contact_book/data/test-contacts.db")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.sessions = create_session_factory(f"sqlite:///{self.database}", Base.metadata)
        clock = lambda: datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
        self.store = ContactStore(self.sessions, now=clock)
        self.client = Client(create_app(store=self.store))

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    @staticmethod
    def contact(**changes) -> dict:
        value = {"name": "Ada Lovelace", "email": "ada@example.test", "phone": "+44 20 0000",
            "company": "Analytical Engines", "job_title": "Programmer", "city": "London",
            "tags": ["friend", "client"]}
        value.update(changes)
        return value

    def test_crud_persists_and_conflicts_are_contextual(self) -> None:
        created = self.client.request("POST", "/api/contacts", json=self.contact())
        self.assertEqual(created.status_code, 201)
        identity = created.json()["id"]
        self.assertEqual(self.client.request("POST", "/api/contacts",
            json=self.contact(name="Another Ada", email="ADA@example.test")).status_code, 409)
        updated = self.client.request("PUT", f"/api/contacts/{identity}",
            json=self.contact(name="Ada King", city="Paris"))
        self.assertEqual((updated.status_code, updated.json()["name"], updated.json()["city"]),
            (200, "Ada King", "Paris"))
        restarted = Client(create_app(store=ContactStore(self.sessions)))
        self.assertEqual(restarted.request("GET", "/api/contacts?q=Paris").json()["total"], 1)
        self.assertEqual(self.client.request("DELETE", f"/api/contacts/{identity}").status_code, 204)
        self.assertEqual(self.client.request("DELETE", f"/api/contacts/{identity}").status_code, 404)

    def test_list_query_order_and_bounds(self) -> None:
        for name, email, city in (("Zulu", "z@example.test", "Boston"),
            ("Alpha", "a@example.test", "Austin"), ("Beta", "b@example.test", "Boston")):
            self.store.create(ContactCreate(**self.contact(name=name, email=email, city=city)))
        first = self.client.request("GET", "/api/contacts?sort=name&page_size=2").json()
        second = self.client.request("GET", "/api/contacts?sort=name&page=2&page_size=2").json()
        filtered = self.client.request("GET", "/api/contacts?q=Boston&sort=email&direction=desc").json()
        sortable = [self.client.request("GET", f"/api/contacts?sort={field}")
            for field in ("name", "email", "company", "job_title", "city")]
        self.assertEqual(([item["name"] for item in first["items"]], first["pages"],
            [item["name"] for item in second["items"]]), (["Alpha", "Beta"], 2, ["Zulu"]))
        self.assertEqual([item["email"] for item in filtered["items"]],
            ["z@example.test", "b@example.test"])
        self.assertTrue(all(response.status_code == 200 for response in sortable))
        self.assertEqual(self.client.request("GET", "/api/contacts?page_size=101").status_code, 422)
        self.assertEqual(self.client.request("GET", "/api/contacts?sort=unknown").status_code, 422)

    def test_seed_is_deterministic_and_repeatable(self) -> None:
        self.assertEqual((seed_contacts(self.store, 40), seed_contacts(self.store, 40)), (40, 0))
        page = self.store.list(page_size=100)
        identity, expected = generated_contact(0)
        actual = next(item for item in page.items if item.id == identity)
        self.assertEqual((page.total, actual.email, actual.company),
            (40, expected.email, expected.company))

    def test_validation_origin_and_missing_records_fail_closed(self) -> None:
        invalid = self.client.request("POST", "/api/contacts", json=self.contact(email="invalid"))
        forbidden = self.client.request("POST", "/api/contacts",
            headers={"Origin": "https://foreign.test"}, json=self.contact())
        missing = self.client.request("PUT", "/api/contacts/missing", json=self.contact())
        self.assertEqual((invalid.status_code, forbidden.status_code, missing.status_code), (422, 403, 404))

    def test_frontend_uses_view_only_monoui_table(self) -> None:
        source = Path("apps/contact_book/frontend/index.tsx").read_text(encoding="utf-8")
        table = Path("packages/monoui/src/table.tsx").read_text(encoding="utf-8")
        self.assertIn("<Table", source)
        self.assertNotIn("fetch(", table)
        self.assertNotIn("useState", table)
        self.assertIn('scope="col"', table)
        self.assertIn('scope={column.rowHeader ? "row" : undefined}', table)


if __name__ == "__main__":
    unittest.main()
