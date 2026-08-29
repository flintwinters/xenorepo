"""Platform contracts shared by every managed FastAPI application."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.responses import JSONResponse
from starlette.requests import Request

from monotools.orchestration.apps import ROOT
from monotools.runtime.http import (
    client_provenance,
    delete_session_cookie,
    domain_error_handler,
    enforce_same_origin,
    json_error,
    require_cookie_principal,
    resolve_cookie_principal,
    same_origin_allowed,
    set_session_cookie,
)
from monotools.runtime.application import create_application
from tests.support import synthetic_app_definition


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

    def test_origin_and_cookie_helpers_preserve_application_rejections(self) -> None:
        accepted = request(headers={"Cookie": "session=known"})
        resolver = lambda value: {"known": "principal"}.get(value)
        self.assertEqual(resolve_cookie_principal(accepted, "session", resolver), "principal")
        self.assertEqual(require_cookie_principal(
            accepted, "session", resolver, ValueError, "Authentication required."), "principal")
        with self.assertRaisesRegex(ValueError, "Authentication required"):
            require_cookie_principal(request(), "session", resolver, ValueError,
                "Authentication required.")

        rejected = enforce_same_origin(request(headers={"Origin": "https://foreign.test"}),
            lambda message: json_error(message, 403))
        self.assertEqual((rejected.status_code, rejected.body),
            (403, b'{"error":"Request origin is not allowed."}'))
        with self.assertRaisesRegex(ValueError, "origin is not allowed"):
            enforce_same_origin(request(headers={"Origin": "https://foreign.test"}), ValueError)

    def test_domain_error_handler_is_configurable(self) -> None:
        class Failure(ValueError):
            kind = "missing"

        handler = domain_error_handler(statuses={"missing": 404})
        response = asyncio.run(handler(request(), Failure("Not found.")))
        self.assertEqual((response.status_code, response.body), (404, b'{"error":"Not found."}'))


class RuntimePlatformTests(unittest.TestCase):
    def test_runtime_exposes_health_and_metadata_declared_documents(self) -> None:
        with TemporaryDirectory(dir=ROOT / "tests", prefix="runtime-") as temporary:
            definition = synthetic_app_definition(Path(temporary))
        with patch("monotools.runtime.application.get_app", return_value=definition) as get_app:
                application = create_application(definition.name)

        get_app.assert_called_once_with(definition.name)
        routes = {route.path: route for route in application.routes if hasattr(route, "path")}
        self.assertEqual(routes["/health"].endpoint(), {"status": "ok"})
        for path, artifact_name in definition.routes:
            with self.subTest(route=path):
                self.assertEqual(Path(routes[path].endpoint()),
                    definition.dist_directory / definition.artifact(artifact_name).output)


if __name__ == "__main__":
    unittest.main()
