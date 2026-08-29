"""Calendar domain and HTTP contract tests."""

from datetime import UTC, datetime
from pathlib import Path
import asyncio
import unittest

import httpx

from apps.calendar.backend.database import CalendarStore
from apps.calendar.backend.server import create_app
from monotools.database import create_session_factory
from apps.calendar.backend.database import Base


class Client:
    def __init__(self, application) -> None:
        self.application = application

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.application),
                base_url="http://calendar.test") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(send())


class CalendarTests(unittest.TestCase):
    database = Path("apps/calendar/data/test-calendar.db")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.sessions = create_session_factory(f"sqlite:///{self.database}", Base.metadata)
        clock = lambda: datetime(2026, 8, 27, 14, 30, tzinfo=UTC)
        self.client = Client(create_app(store=CalendarStore(self.sessions, now=clock)))

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    def event(self, **changes) -> dict:
        value = {"title": "Planning", "date": "2026-08-27", "all_day": False,
            "start_time": "09:00", "end_time": "10:00", "location": None, "notes": None}
        value.update(changes)
        return value

    def test_timezone_initializes_once_and_mutations_require_same_origin(self) -> None:
        first = self.client.request("PUT", "/api/settings/time-zone",
            json={"time_zone": "America/New_York"})
        same = self.client.request("PUT", "/api/settings/time-zone",
            json={"time_zone": "America/New_York"})
        conflict = self.client.request("PUT", "/api/settings/time-zone",
            json={"time_zone": "Europe/Paris"})
        invalid = self.client.request("PUT", "/api/settings/time-zone",
            json={"time_zone": "Nowhere/Imaginary"})
        forbidden = self.client.request("POST", "/api/events",
            headers={"Origin": "https://foreign.test"}, json=self.event())
        self.assertEqual((first.status_code, same.status_code, conflict.status_code,
            invalid.status_code, forbidden.status_code), (200, 200, 409, 422, 403))

    def test_crud_range_ordering_drag_update_and_restart(self) -> None:
        timed = self.client.request("POST", "/api/events", json=self.event(title="Zulu")).json()
        all_day = self.client.request("POST", "/api/events", json=self.event(
            title="Alpha", all_day=True, start_time=None, end_time=None)).json()
        later = self.client.request("POST", "/api/events", json=self.event(
            title="Alpha timed", start_time="11:00", end_time="12:00")).json()
        view = self.client.request("GET",
            "/api/calendar?start=2026-08-01&end=2026-09-01").json()
        self.assertEqual([item["id"] for item in view["events"]],
            [all_day["id"], timed["id"], later["id"]])

        moved = self.client.request("PATCH", f"/api/events/{timed['id']}",
            json={"date": "2026-08-28", "title": "Moved", "notes": "Durable"})
        self.assertEqual((moved.status_code, moved.json()["date"]), (200, "2026-08-28"))
        restarted = Client(create_app(store=CalendarStore(self.sessions)))
        persisted = restarted.request("GET",
            "/api/calendar?start=2026-08-28&end=2026-08-29").json()["events"]
        self.assertEqual((len(persisted), persisted[0]["notes"]), (1, "Durable"))
        self.assertEqual(self.client.request("DELETE", f"/api/events/{timed['id']}").status_code, 204)
        self.assertEqual(self.client.request("DELETE", f"/api/events/{timed['id']}").status_code, 404)

    def test_invalid_events_updates_ranges_and_missing_ids_fail_visibly(self) -> None:
        cases = [self.event(title=" "), self.event(end_time=None),
            self.event(start_time="10:00", end_time="09:00"),
            self.event(all_day=True)]
        self.assertTrue(all(self.client.request("POST", "/api/events", json=value).status_code == 422
            for value in cases))
        created = self.client.request("POST", "/api/events", json=self.event()).json()
        self.assertEqual(self.client.request("PATCH", f"/api/events/{created['id']}",
            json={"all_day": True}).status_code, 422)
        self.assertEqual(self.client.request("PATCH", "/api/events/missing",
            json={"date": "2026-08-28"}).status_code, 404)
        self.assertEqual(self.client.request("GET",
            "/api/calendar?start=2026-09-01&end=2026-08-01").status_code, 422)

    def test_build_is_a_self_contained_typed_preact_client(self) -> None:
        document = Path("apps/calendar/dist/index.html").read_text(encoding="utf-8")
        source = Path("apps/calendar/frontend/index.tsx").read_text(encoding="utf-8")
        client = Path("apps/calendar/frontend/client.ts").read_text(encoding="utf-8")
        styles = Path("apps/calendar/frontend/styles.css").read_text(encoding="utf-8")
        self.assertIn("CALENDAR // 01", document)
        self.assertIn("/api/calendar", document)
        self.assertNotIn("APP_BUNDLE", document)
        self.assertIn('from "@xenorepo/ui";', source)
        self.assertIn('import "./styles.css";', source)
        self.assertIn('import type { components, paths } from "../data/openapi";', client)
        self.assertNotIn('from "lit"', source)
        self.assertNotIn("resize: vertical", styles)


if __name__ == "__main__":
    unittest.main()
