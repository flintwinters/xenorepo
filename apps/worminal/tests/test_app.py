"""Worminal-owned PTY contracts."""

import asyncio
import os
from pathlib import Path
import unittest

from apps.worminal.backend.server import PtySession, terminal_size


class WorminalTests(unittest.TestCase):
    def test_resize_contract_rejects_invalid_dimensions(self) -> None:
        self.assertEqual(terminal_size({"type": "resize", "rows": 24, "columns": 80}), (24, 80))
        for payload in ({"type": "resize", "rows": 0, "columns": 80},
            {"type": "resize", "rows": True, "columns": 80},
            {"type": "resize", "rows": 24, "columns": 1001},
            {"type": "input", "data": "pwd"}):
            self.assertIsNone(terminal_size(payload))

    def test_pty_starts_from_home_and_closes_process_group(self) -> None:
        session = PtySession(shell="/bin/sh")
        pid = session.process.pid

        async def exercise() -> bytes:
            session.write("printf '__WORMINAL__%s\\n' \"$PWD\"\n")
            output = b""
            expected = str(Path.home()).encode()
            while expected not in output:
                output += await asyncio.wait_for(session.read(), 2)
            await session.close()
            return output

        output = asyncio.run(exercise())
        self.assertIn(str(Path.home()).encode(), output)
        self.assertIsNotNone(session.process.poll())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)


if __name__ == "__main__":
    unittest.main()
