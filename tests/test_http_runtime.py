"""Platform contracts shared by every managed FastAPI application."""

from pathlib import Path
import unittest

from fastapi.responses import JSONResponse
from starlette.requests import Request

from tooling.apps import discover_apps
from tooling.http import (
    client_provenance,
    delete_session_cookie,
    json_error,
    same_origin_allowed,
    set_session_cookie,
)


def request(scheme: str = "http", headers: dict[str, str] | None = None) -> Request:
    """Create a repeatable request fixture without a separate HTTP test service."""
    encoded = [(name.lower().encode(), value.encode()) for name, value in (headers or {}).items()]
    return Request({"type": "http", "scheme": scheme, "path": "/", "headers": encoded,
        "client": ("127.0.0.1", 1), "server": ("console.test", 443 if scheme == "https" else 80)})


class HttpPlatformTests(unittest.TestCase):
    def test_same_origin_validation_and_provenance_are_exact(self) -> None:
        accepted = request(headers={"Origin": "http://console.test", "User-Agent": "suite"})
        self.assertTrue(same_origin_allowed(accepted))
        self.assertEqual(client_provenance(accepted), {"client_host": "127.0.0.1",
            "user_agent": "suite", "origin": "http://console.test"})
        self.assertTrue(same_origin_allowed(request()))
        self.assertFalse(same_origin_allowed(request(headers={"Origin": "https://console.test"})))
        self.assertFalse(same_origin_allowed(request(headers={"Origin": "http://foreign.test"})))

    def test_error_envelope_and_session_cookie_policy_are_stable(self) -> None:
        response = json_error("Invalid input.", 422)
        self.assertEqual((response.status_code, response.body), (422, b'{"error":"Invalid input."}'))

        secure = set_session_cookie(JSONResponse({}), request("https"), "session", "secret", 60)
        cookie = secure.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertIn("Secure", cookie)
        cleared = delete_session_cookie(JSONResponse({}), "session")
        self.assertIn("session=\"\"", cleared.headers["set-cookie"])
        self.assertIn("Path=/", cleared.headers["set-cookie"])


class RuntimePlatformTests(unittest.TestCase):
    def test_every_discovered_app_exposes_health_and_root_document(self) -> None:
        for definition in discover_apps():
            with self.subTest(app=definition.name):
                module = __import__(definition.module, fromlist=["app"])
                application = module.app
                routes = {route.path: route for route in application.routes if hasattr(route, "path")}
                self.assertEqual(routes["/health"].endpoint(), {"status": "ok"})
                document = routes["/"].endpoint()
                self.assertEqual(Path(document), definition.dist_directory / "index.html")


if __name__ == "__main__":
    unittest.main()
