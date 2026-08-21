import select
from types import SimpleNamespace
import unittest

from apps.worminal.server import app
from apps.worminal.terminal import PtySession, is_loopback_client


class WorminalTests(unittest.TestCase):
    def test_only_ip_loopback_clients_can_open_shells(self) -> None:
        for host in ("127.0.0.1", "::1"):
            with self.subTest(host=host):
                self.assertTrue(is_loopback_client(SimpleNamespace(client=SimpleNamespace(host=host))))
        for host in ("192.168.1.10", "example.test", ""):
            with self.subTest(host=host):
                self.assertFalse(is_loopback_client(SimpleNamespace(client=SimpleNamespace(host=host))))

    def test_application_exposes_one_terminal_websocket(self) -> None:
        paths = [route.path for route in app.routes if hasattr(route, "path")]
        self.assertEqual(paths.count("/ws/terminal"), 1)

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
