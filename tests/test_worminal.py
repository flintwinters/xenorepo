import select
import asyncio
import os
from pathlib import Path
import pwd
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import select as sa_select

from apps.worminal.database import ServerSettings, WorkspaceRepository, create_session_factory
from apps.worminal.server import (ACCESS_COOKIE, TerminalManager, access_cookie_value, app,
    create_app, PasswordChangeInput, remote_access_authorized)
from apps.worminal.terminal import PtySession, is_loopback_client, resolve_shell_account


class WorminalTests(unittest.TestCase):
    database = Path("apps/worminal/data/test-worminal.db")

    def test_user_service_runs_managed_uvicorn_with_live_frontend_builds(self) -> None:
        unit = Path("apps/worminal/worminal.service").read_text(encoding="utf-8")

        self.assertIn("WantedBy=default.target", unit)
        self.assertIn("Environment=WORMINAL_ACCESS_TOKEN=felix", unit)
        self.assertIn("ExecStart=/usr/bin/authbind --deep %h/.local/bin/uv run python "
            "manage.py serve worminal "
            "--watch --host 0.0.0.0 --port 80", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertNotIn("ExecStartPre", unit)

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.sessions = create_session_factory(f"sqlite:///{self.database}")
        self.repository = WorkspaceRepository(self.sessions)

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    def test_only_ip_loopback_clients_can_open_shells(self) -> None:
        for host in ("127.0.0.1", "::1"):
            with self.subTest(host=host):
                self.assertTrue(is_loopback_client(SimpleNamespace(client=SimpleNamespace(host=host))))
        for host in ("192.168.1.10", "example.test", ""):
            with self.subTest(host=host):
                self.assertFalse(is_loopback_client(SimpleNamespace(client=SimpleNamespace(host=host))))

    def test_remote_access_requires_the_configured_password(self) -> None:
        token = "test-remote-access-token"
        self.repository.initialize(token)
        self.assertFalse(remote_access_authorized(None, self.repository))
        self.assertFalse(remote_access_authorized("wrong-token", self.repository))
        self.assertTrue(remote_access_authorized(token, self.repository))
        version = self.repository.access_session_version()
        self.assertNotEqual(access_cookie_value(version), token)

    def test_access_password_is_salted_persisted_and_seeded_only_once(self) -> None:
        original = "initial-environment-password"
        self.repository.initialize(original)
        with self.sessions() as session:
            settings = session.get(ServerSettings, 1)
            self.assertNotEqual(settings.password_digest, original.encode())
            self.assertNotIn(original.encode(), settings.password_digest)
            self.assertEqual(len(settings.password_salt), 16)
        self.sessions.kw["bind"].dispose()
        self.sessions = create_session_factory(f"sqlite:///{self.database}")
        restarted = WorkspaceRepository(self.sessions)
        restarted.initialize("changed-environment-password")

        self.assertTrue(restarted.verify_access_password(original))
        self.assertFalse(restarted.verify_access_password("changed-environment-password"))

    def test_unconfigured_settings_accept_the_first_later_environment_password(self) -> None:
        workspace = self.repository.initialize()
        self.repository.initialize("later-environment-password")

        self.assertEqual(self.repository.shared_workspace(), workspace)
        self.assertTrue(self.repository.verify_access_password("later-environment-password"))

    def test_password_change_rotates_the_persistent_access_session(self) -> None:
        self.repository.initialize("current-password")
        previous_version = self.repository.access_session_version()
        self.assertFalse(self.repository.change_access_password(
            "wrong-password", "replacement-password"))
        self.assertEqual(self.repository.access_session_version(), previous_version)
        self.assertTrue(self.repository.change_access_password(
            "current-password", "replacement-password"))
        replacement_version = self.repository.access_session_version()

        self.assertNotEqual(replacement_version, previous_version)
        self.assertFalse(self.repository.verify_access_password("current-password"))
        self.assertTrue(self.repository.verify_access_password("replacement-password"))
        self.sessions.kw["bind"].dispose()
        self.sessions = create_session_factory(f"sqlite:///{self.database}")
        self.assertEqual(WorkspaceRepository(self.sessions).access_session_version(),
            replacement_version)

    def test_application_exposes_one_terminal_websocket(self) -> None:
        paths = [route.path for route in app.routes if hasattr(route, "path")]
        self.assertEqual(paths.count("/ws/terminal/{window_id}"), 1)

    def test_workspace_persists_window_geometry_and_terminal_text(self) -> None:
        workspace = self.repository.create_workspace()
        window = {"id": "21db2107-fd03-45bd-a1a6-7d31e9b458ae", "title": "shell-1",
            "x": 60, "y": 48, "width": 720, "height": 480, "z": 4,
            "minimized": False, "maximized": False}
        self.repository.replace_windows(workspace, [window])
        self.repository.append_output(workspace, window["id"], b"$ echo durable\r\ndurable\r\n")
        self.sessions.kw["bind"].dispose()
        self.sessions = create_session_factory(f"sqlite:///{self.database}")
        restarted = WorkspaceRepository(self.sessions)

        self.assertEqual(restarted.windows(workspace), [window])
        self.assertEqual(restarted.transcript(workspace, window["id"]),
            b"$ echo durable\r\ndurable\r\n")

    def test_shared_workspace_adopts_existing_server_desktop(self) -> None:
        workspace = self.repository.create_workspace()
        self.assertEqual(self.repository.shared_workspace(), workspace)
        self.assertEqual(self.repository.shared_workspace(), workspace)

    def test_shared_workspace_remains_canonical_when_another_workspace_is_updated(self) -> None:
        canonical = self.repository.create_workspace()
        self.assertEqual(self.repository.shared_workspace(), canonical)
        other = self.repository.create_workspace()
        self.repository.replace_shortcuts(other, [{"action": "new-shell", "key": "N",
            "control": True, "alt": False, "shift": False, "meta": False}])

        self.assertEqual(self.repository.shared_workspace(), canonical)
        with self.sessions() as session:
            settings = session.scalar(sa_select(ServerSettings))
            self.assertEqual(settings.canonical_workspace_id, canonical)

    def test_password_change_api_requires_current_password_and_same_origin(self) -> None:
        with patch.dict(os.environ, {"WORMINAL_ACCESS_TOKEN": "current-password"}):
            application = create_app(f"sqlite:///{self.database}")
        endpoint = next(route.endpoint for route in application.routes
            if getattr(route, "path", None) == "/api/access/password")
        repository = application.state.repository
        previous_cookie = access_cookie_value(repository.access_session_version())

        def request(origin: str | None = None) -> Request:
            headers = [(b"host", b"testserver")]
            if origin:
                headers.append((b"origin", origin.encode()))
            return Request({"type": "http", "scheme": "http", "path": "/api/access/password",
                "headers": headers, "client": ("127.0.0.1", 1),
                "server": ("testserver", 80)})

        with self.assertRaises(HTTPException) as invalid:
            endpoint(PasswordChangeInput(current_password="wrong-password",
                new_password="replacement-password"), request())
        self.assertEqual(invalid.exception.status_code, 401)
        with self.assertRaises(HTTPException) as cross_origin:
            endpoint(PasswordChangeInput(current_password="current-password",
                new_password="replacement-password"), request("https://foreign.example"))
        self.assertEqual(cross_origin.exception.status_code, 403)
        changed = endpoint(PasswordChangeInput(current_password="current-password",
            new_password="replacement-password"), request())

        self.assertEqual(changed.status_code, 204)
        self.assertIn(f"{ACCESS_COOKIE}=", changed.headers["set-cookie"])
        self.assertNotIn(previous_cookie, changed.headers["set-cookie"])
        self.assertFalse(repository.verify_access_password("current-password"))
        self.assertTrue(repository.verify_access_password("replacement-password"))

    def test_replacing_windows_does_not_discard_its_transcript(self) -> None:
        workspace = self.repository.create_workspace()
        window = {"id": "21db2107-fd03-45bd-a1a6-7d31e9b458ae", "title": "shell-1",
            "x": 32, "y": 30, "width": 650, "height": 410, "z": 2,
            "minimized": False, "maximized": False}
        self.repository.replace_windows(workspace, [window])
        self.repository.append_output(workspace, window["id"], b"previous output")
        window["x"], window["width"], window["minimized"] = 92, 800, True
        self.repository.replace_windows(workspace, [window])

        self.assertEqual(self.repository.transcript(workspace, window["id"]), b"previous output")

    def test_workspace_persists_a_custom_new_shell_shortcut(self) -> None:
        workspace = self.repository.create_workspace()
        shortcut = {"action": "new-shell", "key": "N", "control": True,
            "alt": True, "shift": False, "meta": False}
        self.assertEqual(self.repository.shortcuts(workspace)[0]["key"], "Meta")
        self.repository.replace_shortcuts(workspace, [shortcut])
        self.sessions.kw["bind"].dispose()
        self.sessions = create_session_factory(f"sqlite:///{self.database}")

        self.assertEqual(WorkspaceRepository(self.sessions).shortcuts(workspace), [shortcut])

    def test_pty_session_runs_a_real_shell_and_closes_its_process(self) -> None:
        session = PtySession("/bin/sh")
        self.addCleanup(session.close)
        session.write("printf 'worminal-checkpoint\\n'\nexit\n")
        output = bytearray()
        for _ in range(20):
            readable, _, _ = select.select([session.master], [], [], 0.25)
            if readable:
                try:
                    output.extend(session.read())
                except OSError:
                    break
            if session.process.poll() is not None:
                break
        session.process.wait(timeout=2)

        self.assertIn(b"worminal-checkpoint", output)
        session.close()
        self.assertTrue(session.closed)
        self.assertIsNotNone(session.process.returncode)

    def test_selected_terminal_user_controls_the_shell_identity(self) -> None:
        account = pwd.getpwuid(os.geteuid())
        self.assertEqual(resolve_shell_account(account.pw_name).uid, account.pw_uid)
        with self.assertRaisesRegex(ValueError, "Unknown terminal user"):
            resolve_shell_account("worminal-user-that-does-not-exist")
        session = PtySession("/bin/sh", user=account.pw_name)
        self.addCleanup(session.close)
        session.write("id -un\nexit\n")
        output = bytearray()
        while session.process.poll() is None:
            readable, _, _ = select.select([session.master], [], [], 0.25)
            if readable:
                try:
                    output.extend(session.read())
                except OSError:
                    break
        session.process.wait(timeout=2)

        self.assertIn(account.pw_name.encode(), output)

    def test_terminal_manager_broadcasts_one_pty_to_multiple_views(self) -> None:
        workspace = self.repository.create_workspace()
        window = {"id": "21db2107-fd03-45bd-a1a6-7d31e9b458ae", "title": "shell-1",
            "x": 32, "y": 30, "width": 650, "height": 410, "z": 2,
            "minimized": False, "maximized": False}
        self.repository.replace_windows(workspace, [window])

        class View:
            def __init__(self) -> None:
                self.output = bytearray()

            async def send_bytes(self, output: bytes) -> None:
                self.output.extend(output)

        async def exercise() -> None:
            manager = TerminalManager(None, self.repository)
            first, second = View(), View()
            session = manager.attach(window["id"], first)
            self.assertIs(manager.attach(window["id"], second), session)
            session.write("printf 'multi-view-check\\n'\n")
            for _ in range(40):
                if b"multi-view-check" in first.output and b"multi-view-check" in second.output:
                    break
                await asyncio.sleep(0.05)
            manager.close_all()
            self.assertIn(b"multi-view-check", first.output)
            self.assertIn(b"multi-view-check", second.output)

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
