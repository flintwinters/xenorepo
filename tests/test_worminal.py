import select
from base64 import b64encode
import os
from pathlib import Path
import pwd
from types import SimpleNamespace
import unittest

from apps.worminal.database import WorkspaceRepository, create_session_factory
from apps.worminal.server import app, remote_access_authorized
from apps.worminal.terminal import PtySession, is_loopback_client, resolve_shell_account


class WorminalTests(unittest.TestCase):
    database = Path("apps/worminal/data/test-worminal.db")

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

    def test_remote_access_requires_the_configured_basic_authentication(self) -> None:
        token = "test-remote-access-token"
        authorization = "Basic " + b64encode(f"worminal:{token}".encode()).decode()
        self.assertFalse(remote_access_authorized(None, token))
        self.assertFalse(remote_access_authorized(authorization, None))
        self.assertFalse(remote_access_authorized(authorization, "wrong-token"))
        self.assertTrue(remote_access_authorized(authorization, token))

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


if __name__ == "__main__":
    unittest.main()
