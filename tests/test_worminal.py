import select
from pathlib import Path
from types import SimpleNamespace
import unittest

from apps.worminal.database import WorkspaceRepository, create_session_factory
from apps.worminal.server import app
from apps.worminal.terminal import PtySession, is_loopback_client


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


if __name__ == "__main__":
    unittest.main()
