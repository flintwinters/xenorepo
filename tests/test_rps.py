"""Curated persistence, API, and competitive-domain contracts for Rock Paper Scissors."""

import json
from pathlib import Path
import unittest

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from apps.rps.auth import credential_digest
from apps.rps.database import (
    ConnectionSession,
    DomainError,
    GuestCredential,
    Match,
    MatchmakingEntry,
    MatchParticipant,
    Player,
    Round,
    RpsRepository,
    Throw,
    create_session_factory,
    now,
    throw_result,
)


class RpsTests(unittest.TestCase):
    database = Path("apps/rps/data/test-rps.db")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.sessions = create_session_factory(f"sqlite:///{self.database}")
        self.repository = RpsRepository(self.sessions)

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    def guest(self, token: str) -> Player:
        return self.repository.create_guest(token)

    def test_every_application_title_is_rock_paper_scissors(self) -> None:
        from apps.rps.server import create_app
        from tooling.apps import get_app

        title = "Rock Paper Scissors"
        document = Path("apps/rps/frontend/index.html").read_text(encoding="utf-8")
        self.assertEqual(get_app("rps").title, title)
        application = create_app(f"sqlite:///{self.database}")
        try:
            self.assertEqual(application.title, title)
        finally:
            application.state.repository.sessions.kw["bind"].dispose()
        self.assertIn(f"<title>{title}</title>", document)
        self.assertIn(f'<span class="brand">{title}</span>', document)

    def test_operator_console_document_follows_repository_ui_direction(self) -> None:
        document = Path("apps/rps/frontend/index.html").read_text(encoding="utf-8")
        for marker in ("grid-template-rows:28px 1fr",
            'class="utility"', 'class="mosaic"',
            'class="pane arena-index"', 'class="pane battle"',
            'class="pane ledger"',
            'class="index">01', 'id="round-log"', "position:sticky",
            'id="top-matches"', 'id="recent-results"', 'data-watch',
            '"spectator_state"', '"arena_snapshot"',
            'id="landing"', 'id="play-form"', 'id="landing-matches"',
            'class="key play"', 'p.competitive_streak', 'send("queue_join")',
            'class="landing-utility"', 'class="landing-mosaic"',
            'class="landing-status"', 'ENTER ARENA',
            'error.status=r.status', 'if(e.status===404)', '● WRONG SERVICE',
            'function announce(', 'MATCH START · YOU VS', 'MATCH WON',
            'MATCH LOST', 'OPPONENT READY · YOUR THROW',
            'MATCHMAKING · SEARCHING FOR OPPONENT', 'classList.toggle("ready"',
            'CONNECTION LOST · RECONNECTING',
            "@media(max-width:850px)", "@media(max-width:590px)"):
            with self.subTest(marker=marker):
                self.assertIn(marker, document)
        for forbidden in ("radial-gradient", "border-radius", "@keyframes",
            "animation:", "transition:"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, document)
        opponent = document.index('id="opponent-strip"')
        instrument = document.index('class="instrument"')
        you = document.index('id="you-strip"')
        self.assertLess(opponent, instrument)
        self.assertLess(instrument, you)
        for redundant in ('class="pane inspector"', 'class="status"',
            'PAIRING GAP EXPANDS', '<dt>FORMAT</dt>', 'id="system-clock"',
            'class="landing-card"', 'box-shadow:0 12px 30px'):
            with self.subTest(redundant=redundant):
                self.assertNotIn(redundant, document)
        self.assertLess(document.index('id="nickname"'),
            document.index('class="key play"'))

    def test_all_nine_throw_pairs_have_antisymmetric_results(self) -> None:
        expected = {
            ("rock", "rock"): 0, ("rock", "paper"): -1, ("rock", "scissors"): 1,
            ("paper", "rock"): 1, ("paper", "paper"): 0, ("paper", "scissors"): -1,
            ("scissors", "rock"): -1, ("scissors", "paper"): 1,
            ("scissors", "scissors"): 0,
        }
        self.assertEqual({pair: throw_result(*pair) for pair in expected}, expected)
        with self.assertRaisesRegex(ValueError, "rock, paper, or scissors"):
            throw_result("lizard", "rock")

    def test_guest_credentials_restore_without_persisting_raw_secret(self) -> None:
        raw = "opaque-guest-credential"
        player = self.guest(raw)
        restored = self.repository.restore_guest(raw)
        self.assertEqual(restored.id, player.id)
        self.assertIsNone(self.repository.restore_guest("incorrect"))
        with self.sessions() as session:
            credential = session.scalar(select(GuestCredential))
            self.assertEqual(credential.digest, credential_digest(raw))
            self.assertNotIn(raw, credential.digest)
        renamed = self.repository.rename(player.id, "  Ada  ")
        self.assertEqual(renamed.nickname, "Ada")
        with self.assertRaisesRegex(DomainError, "2–24"):
            self.repository.rename(player.id, "x")

    def test_connection_queue_and_relational_constraints_preserve_facts(self) -> None:
        player = self.guest("player")
        connection_id = self.repository.open_connection(player.id,
            {"client_host": "127.0.0.1", "user_agent": "tests", "origin": None})
        entry = self.repository.join_queue(player.id)
        with self.assertRaisesRegex(DomainError, "already queued"):
            self.repository.join_queue(player.id)
        self.repository.leave_queue(entry.id)
        self.repository.close_connection(connection_id)
        with self.sessions() as session:
            connection = session.get(ConnectionSession, connection_id)
            queued = session.get(MatchmakingEntry, entry.id)
            self.assertIsNotNone(connection.disconnected_at)
            self.assertEqual((queued.state, queued.match_id), ("left", None))
        with self.assertRaises(IntegrityError), self.sessions.begin() as session:
            session.add(ConnectionSession(id="invalid", player_id="missing",
                connected_at=now(), disconnected_at=None, client_host=None,
                user_agent=None, origin=None))

    def test_decisive_ranked_match_persists_and_updates_streaks(self) -> None:
        first, second = self.guest("first"), self.guest("second")
        with self.sessions.begin() as session:
            session.get(Player, second.id).competitive_streak = 3
        match = self.repository.create_match(first.id, second.id)
        concealed = self.repository.submit_throw(match.id, first.id, "rock")
        self.assertEqual(concealed["state"], "concealed")
        result = self.repository.submit_throw(match.id, second.id, "scissors")
        self.assertEqual((result["state"], result["outcome"], result["winner_id"]),
            ("completed", "decisive", first.id))

        restarted_sessions = create_session_factory(f"sqlite:///{self.database}")
        try:
            restarted = RpsRepository(restarted_sessions)
            persisted = restarted.match_state(match.id)
            self.assertEqual(persisted["rounds"], [{"number": 1, "state": "resolved",
                "outcome": "decisive", "winner_id": first.id}])
            with restarted_sessions() as session:
                self.assertEqual(session.get(Player, first.id).competitive_streak, 1)
                self.assertEqual(session.get(Player, second.id).competitive_streak, 0)
                counts = {model.__tablename__: session.scalar(
                    select(func.count()).select_from(model)) for model in
                    (Player, GuestCredential, Match, MatchParticipant, Round, Throw)}
            self.assertEqual(counts, {"players": 2, "guest_credentials": 2, "matches": 1,
                "match_participants": 2, "rounds": 1, "throws": 2})
        finally:
            restarted_sessions.kw["bind"].dispose()

    def test_state_machine_rejects_illegal_and_duplicate_transitions(self) -> None:
        first, second, outsider = self.guest("first"), self.guest("second"), self.guest("third")
        match = self.repository.create_match(first.id, second.id)
        with self.assertRaisesRegex(DomainError, "not a participant"):
            self.repository.submit_throw(match.id, outsider.id, "rock")
        with self.assertRaisesRegex(DomainError, "rock, paper, or scissors"):
            self.repository.submit_throw(match.id, first.id, "water")
        self.repository.submit_throw(match.id, first.id, "paper")
        with self.assertRaisesRegex(DomainError, "already thrown"):
            self.repository.submit_throw(match.id, first.id, "paper")
        self.repository.submit_throw(match.id, second.id, "rock")
        with self.assertRaisesRegex(DomainError, "already complete"):
            self.repository.submit_throw(match.id, second.id, "scissors")
        with self.assertRaisesRegex(DomainError, "distinct players"):
            self.repository.create_match(first.id, first.id)

    def test_five_ties_end_in_draw_without_changing_streaks(self) -> None:
        first, second = self.guest("first"), self.guest("second")
        with self.sessions.begin() as session:
            session.get(Player, first.id).competitive_streak = 4
            session.get(Player, second.id).competitive_streak = 2
        match = self.repository.create_match(first.id, second.id)
        for round_number in range(1, 6):
            self.repository.submit_throw(match.id, first.id, "rock")
            state = self.repository.submit_throw(match.id, second.id, "rock")
            self.assertEqual(state["round"], round_number)
        self.assertEqual((state["state"], state["outcome"]), ("completed", "draw"))
        self.assertEqual(len(self.repository.match_state(match.id)["rounds"]), 5)
        with self.sessions() as session:
            self.assertEqual((session.get(Player, first.id).competitive_streak,
                session.get(Player, second.id).competitive_streak), (4, 2))

    def test_ranked_forfeit_and_unranked_rematch_have_distinct_streak_effects(self) -> None:
        first, second = self.guest("first"), self.guest("second")
        ranked = self.repository.create_match(first.id, second.id)
        forfeited = self.repository.forfeit(ranked.id, second.id)
        self.assertEqual((forfeited["outcome"], forfeited["winner_id"]),
            ("forfeit", first.id))
        with self.assertRaisesRegex(DomainError, "Rematches must be unranked"):
            self.repository.create_match(first.id, second.id, ranked=True,
                rematch_of_id=ranked.id)
        rematch = self.repository.create_match(first.id, second.id, ranked=False,
            rematch_of_id=ranked.id)
        self.repository.submit_throw(rematch.id, first.id, "rock")
        self.repository.submit_throw(rematch.id, second.id, "paper")
        with self.sessions() as session:
            self.assertEqual((session.get(Player, first.id).competitive_streak,
                session.get(Player, second.id).competitive_streak), (1, 0))
            self.assertFalse(session.get(Match, rematch.id).ranked)
            self.assertEqual(session.get(Match, rematch.id).rematch_of_id, ranked.id)

    def test_session_api_issues_restores_and_renames_http_only_guest(self) -> None:
        from starlette.requests import Request
        from apps.rps.server import COOKIE, NicknameInput, create_app

        application = create_app(f"sqlite:///{self.database}")
        self.addCleanup(application.state.repository.sessions.kw["bind"].dispose)
        endpoints = {route.path + ":" + next(iter(route.methods)): route.endpoint
            for route in application.routes if getattr(route, "methods", None)}

        def request(headers: dict[str, str] | None = None) -> Request:
            encoded = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
            return Request({"type": "http", "scheme": "http", "path": "/",
                "headers": encoded, "client": ("127.0.0.1", 1),
                "server": ("testserver", 80)})

        created = endpoints["/api/session:GET"](request())
        self.assertEqual(created.status_code, 201)
        initial = json.loads(created.body)
        cookie = created.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        session_cookie = cookie.split(";", 1)[0]
        restored = endpoints["/api/session:GET"](request({"Cookie": session_cookie}))
        self.assertEqual(json.loads(restored.body)["id"], initial["id"])
        updated = endpoints["/api/session:PATCH"](
            NicknameInput(nickname="Grace"), request({"Cookie": session_cookie}))
        self.assertEqual(updated["nickname"], "Grace")
        self.assertTrue(session_cookie.startswith(f"{COOKIE}="))


if __name__ == "__main__":
    unittest.main()
