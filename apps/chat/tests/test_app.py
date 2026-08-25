"""Chat-owned product contracts."""

from pathlib import Path
import unittest

from apps.chat.database import ChatRepository, create_session_factory


class ChatTests(unittest.TestCase):
    def test_messages_are_durable_across_repository_restart(self) -> None:
        database = Path("apps/chat/data/test-owned-chat.db")
        database.unlink(missing_ok=True)
        self.addCleanup(database.unlink, missing_ok=True)
        url = f"sqlite:///{database}"
        first_sessions = create_session_factory(url)
        self.addCleanup(first_sessions.kw["bind"].dispose)
        first = ChatRepository(first_sessions)
        session_id = first.open_session({
            "client_host": "127.0.0.1", "user_agent": "test", "origin": None,
        })
        first.identify(session_id, "0f314f25-e6af-49fe-80be-bfb9505b1071", "Ada")
        message = first.add(session_id, "Ada", "Owned suite.", "owned-1")
        second_sessions = create_session_factory(url)
        self.addCleanup(second_sessions.kw["bind"].dispose)
        self.assertEqual(ChatRepository(second_sessions).all(), [message])


if __name__ == "__main__":
    unittest.main()
