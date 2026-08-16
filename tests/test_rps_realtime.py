"""Deterministic multi-client contracts for the live Rock Paper Scissors arena."""

import json
from pathlib import Path
import unittest

from sqlalchemy import select

from apps.rps.arena import ArenaCoordinator, QueueRecord, permitted_streak_difference
from apps.rps.database import Match, MatchmakingEntry, Player, Round, RpsRepository, Throw
from apps.rps.database import create_session_factory
from tests.support import FakeClock, FakeScheduler, SocketDouble, run_async


class RpsRealtimeTests(unittest.TestCase):
    database = Path("apps/rps/data/test-rps-realtime.db")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.clock = FakeClock()
        self.scheduler = FakeScheduler(self.clock)
        self.sessions = create_session_factory(f"sqlite:///{self.database}")
        self.repository = RpsRepository(self.sessions, self.clock.now)
        self.arena = ArenaCoordinator(self.repository, self.clock, self.scheduler)

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    def guest(self, token: str, streak: int = 0) -> Player:
        player = self.repository.create_guest(token)
        if streak:
            with self.sessions.begin() as session:
                session.get(Player, player.id).competitive_streak = streak
            player = self.repository.player(player.id)
        return player

    def connect(self, player: Player) -> SocketDouble:
        socket = SocketDouble()
        run_async(self.arena.connect(socket, player))
        return socket

    def matched_pair(self) -> tuple[Player, SocketDouble, Player, SocketDouble, str]:
        first, second = self.guest("first"), self.guest("second")
        first_socket, second_socket = self.connect(first), self.connect(second)
        run_async(self.arena.join_queue(first.id, "join-first"))
        run_async(self.arena.join_queue(second.id, "join-second"))
        match_id = self.arena.player_matches[first.id]
        return first, first_socket, second, second_socket, match_id

    def test_matchmaking_minimizes_difference_then_uses_oldest_entry(self) -> None:
        first, second, third = self.guest("a"), self.guest("b"), self.guest("c")
        entries = [self.repository.join_queue(player.id) for player in (first, second, third)]
        joined = self.clock.now()
        self.clock.value = joined.replace(second=10)
        self.arena.queue = {
            first.id: QueueRecord(first.id, entries[0].id, 0, joined),
            second.id: QueueRecord(second.id, entries[1].id, 2, joined),
            third.id: QueueRecord(third.id, entries[2].id, 3, joined),
        }
        pair = self.arena._best_pair()
        self.assertEqual({record.player_id for record in pair}, {second.id, third.id})

        self.arena.queue[first.id] = QueueRecord(first.id, entries[0].id, 1, joined)
        self.arena.queue[second.id] = QueueRecord(second.id, entries[1].id, 0,
            joined.replace(microsecond=1))
        self.arena.queue[third.id] = QueueRecord(third.id, entries[2].id, 2,
            joined.replace(microsecond=2))
        pair = self.arena._best_pair()
        self.assertEqual(tuple(record.player_id for record in pair), (first.id, second.id))

    def test_matchmaking_gap_expands_once_per_five_seconds_then_becomes_unlimited(self) -> None:
        boundaries = {0: 0, 4.999: 0, 5: 1, 9.999: 1, 10: 2,
            25: 5, 29.999: 5, 30: None, 300: None}
        self.assertEqual({elapsed: permitted_streak_difference(elapsed)
            for elapsed in boundaries}, boundaries)

    def test_matchmaking_widens_at_five_seconds_and_assigns_atomically(self) -> None:
        first, second = self.guest("first"), self.guest("second", streak=1)
        first_socket, second_socket = self.connect(first), self.connect(second)
        run_async(self.arena.join_queue(first.id, "join-first"))
        run_async(self.arena.join_queue(second.id, "join-second"))
        run_async(self.scheduler.advance(4.999))
        self.assertFalse(self.arena.matches)
        run_async(self.scheduler.advance(0.001))
        self.assertEqual(len(self.arena.matches), 1)
        self.assertTrue(any(event["type"] == "match_assignment" for event in first_socket.events))
        self.assertTrue(any(event["type"] == "match_assignment" for event in second_socket.events))
        with self.sessions() as session:
            entries = session.scalars(select(MatchmakingEntry)).all()
            self.assertEqual({entry.state for entry in entries}, {"matched"})
            self.assertEqual(len({entry.match_id for entry in entries}), 1)

    def test_first_throw_stays_concealed_then_both_reveal_and_persist(self) -> None:
        first, first_socket, second, second_socket, match_id = self.matched_pair()
        first_socket.events.clear()
        second_socket.events.clear()
        run_async(self.arena.submit_throw(first.id, "rock", "throw-first"))
        concealed_payload = json.dumps(first_socket.events)
        self.assertNotIn("rock", concealed_payload)
        self.assertEqual(first_socket.events[-1]["type"], "round_state")
        self.assertTrue(first_socket.events[-1]["submitted"])
        self.assertTrue(second_socket.events[-1]["opponent_submitted"])
        run_async(self.arena.submit_throw(first.id, "paper", "throw-first"))
        with self.sessions() as session:
            self.assertEqual(len(session.scalars(select(Throw)).all()), 1)

        run_async(self.arena.submit_throw(second.id, "scissors", "throw-second"))
        reveal = next(event for event in first_socket.events if event["type"] == "round_reveal")
        self.assertEqual(reveal["throws"], {first.id: "rock", second.id: "scissors"})
        self.assertEqual(first_socket.events[-1]["type"], "match_result")
        with self.sessions() as session:
            match = session.get(Match, match_id)
            self.assertEqual((match.state, match.winner_id), ("completed", first.id))

    def test_completed_players_rejoin_matchmaking_after_one_second(self) -> None:
        first, first_socket, second, second_socket, match_id = self.matched_pair()
        run_async(self.arena.submit_throw(first.id, "rock", "throw-first"))
        run_async(self.arena.submit_throw(second.id, "scissors", "throw-second"))
        self.assertNotIn(first.id, self.arena.queue)
        self.assertNotIn(second.id, self.arena.queue)

        run_async(self.scheduler.advance(0.999))
        self.assertNotIn(first.id, self.arena.queue)
        self.assertNotIn(second.id, self.arena.queue)

        run_async(self.scheduler.advance(0.001))
        self.assertIn(first.id, self.arena.queue)
        self.assertIn(second.id, self.arena.queue)
        self.assertTrue(any(event == {"type": "queue_state", "queued": True}
            for event in first_socket.events))
        self.assertTrue(any(event == {"type": "queue_state", "queued": True}
            for event in second_socket.events))

    def test_mutual_rematch_starts_an_unranked_replay_after_result_pause(self) -> None:
        first, _, second, _, match_id = self.matched_pair()
        run_async(self.arena.submit_throw(first.id, "rock", "throw-first"))
        run_async(self.arena.submit_throw(second.id, "scissors", "throw-second"))
        run_async(self.arena.request_rematch(first.id, match_id, "rematch-first"))
        run_async(self.arena.request_rematch(second.id, match_id, "rematch-second"))

        run_async(self.scheduler.advance(1))
        rematch_id = self.arena.player_matches[first.id]
        self.assertEqual(rematch_id, self.arena.player_matches[second.id])
        self.assertNotEqual(rematch_id, match_id)
        with self.sessions() as session:
            rematch = session.get(Match, rematch_id)
            self.assertEqual((rematch.ranked, rematch.rematch_of_id), (False, match_id))

    def test_selection_deadline_forfeits_the_only_missing_player(self) -> None:
        first, first_socket, second, second_socket, match_id = self.matched_pair()
        run_async(self.arena.submit_throw(first.id, "paper", "throw-first"))
        run_async(self.scheduler.advance(10))
        self.assertEqual(first_socket.events[-1]["outcome"], "forfeit")
        self.assertEqual(first_socket.events[-1]["winner_id"], first.id)

    def test_selection_deadline_turns_two_missing_players_into_a_draw(self) -> None:
        first, first_socket, second, second_socket, match_id = self.matched_pair()
        run_async(self.scheduler.advance(10))
        self.assertEqual(first_socket.events[-1]["outcome"], "draw")
        with self.sessions() as session:
            round_ = session.get(Round, (match_id, 1))
            self.assertEqual(round_.state, "cancelled")

    def test_last_socket_disconnect_has_five_second_credential_recovery(self) -> None:
        first, first_socket, second, second_socket, match_id = self.matched_pair()
        extra = self.connect(first)
        run_async(self.arena.disconnect(first_socket))
        self.assertNotIn(first.id, self.arena.matches[match_id].disconnected)
        run_async(self.arena.disconnect(extra))
        self.assertIn(first.id, self.arena.matches[match_id].disconnected)
        run_async(self.scheduler.advance(4.999))
        self.assertIn(match_id, self.arena.matches)

        replacement = self.connect(self.repository.player(first.id))
        self.assertNotIn(first.id, self.arena.matches[match_id].disconnected)
        self.assertTrue(any(event["type"] == "match_assignment" for event in replacement.events))
        run_async(self.scheduler.advance(0.002))
        self.assertIn(match_id, self.arena.matches)

        run_async(self.arena.disconnect(replacement))
        run_async(self.scheduler.advance(5))
        self.assertNotIn(match_id, self.arena.matches)
        self.assertEqual(second_socket.events[-1]["outcome"], "forfeit")

    def test_stale_socket_is_evicted_while_healthy_opponent_completes(self) -> None:
        first, first_socket, second, second_socket, match_id = self.matched_pair()
        first_socket.fail_sends = True
        run_async(self.arena.submit_throw(second.id, "paper", "throw-second"))
        self.assertEqual(len(self.arena.connections), 1)
        self.assertIn(first.id, self.arena.matches[match_id].disconnected)
        run_async(self.scheduler.advance(5))
        self.assertEqual(second_socket.events[-1]["type"], "match_result")
        self.assertEqual(second_socket.events[-1]["winner_id"], second.id)

    def test_queue_leave_is_durable_and_idempotent_by_client_id(self) -> None:
        waiting = self.guest("waiting", streak=7)
        socket = self.connect(waiting)
        run_async(self.arena.join_queue(waiting.id, "join"))
        run_async(self.arena.leave_queue(waiting.id, "leave"))
        self.assertEqual(socket.events[-1], {"type": "queue_state", "queued": False})
        run_async(self.arena.leave_queue(waiting.id, "leave"))
        with self.sessions() as session:
            entry = session.scalar(select(MatchmakingEntry))
            self.assertEqual(entry.state, "left")

    def test_resolved_round_makes_its_original_timer_stale(self) -> None:
        first, first_socket, second, second_socket, match_id = self.matched_pair()
        run_async(self.arena.submit_throw(first.id, "rock", "one"))
        run_async(self.arena.submit_throw(second.id, "rock", "two"))
        self.assertEqual(self.arena.matches[match_id].round_number, 2)
        run_async(self.scheduler.advance(9.999))
        self.assertIn(match_id, self.arena.matches)

    def test_arena_snapshot_ranks_matches_and_reports_public_counts(self) -> None:
        players = [self.guest(str(index), streak) for index, streak in
            enumerate((2, 2, 9, 9, 5, 5))]
        sockets = [self.connect(player) for player in players]
        for index, player in enumerate(players):
            run_async(self.arena.join_queue(player.id, f"join-{index}"))
        snapshot = [event for event in sockets[0].events
            if event["type"] == "arena_snapshot"][-1]
        self.assertEqual((snapshot["visitors"], snapshot["queue_size"],
            snapshot["active_matches"]), (6, 0, 3))
        rankings = [(item["highest_streak"], item["combined_streak"])
            for item in snapshot["top_matches"]]
        self.assertEqual(rankings, [(9, 18), (5, 10), (2, 4)])

    def test_spectator_subscription_is_isolated_and_never_exposes_pending_throw(self) -> None:
        first, _, second, _, match_id = self.matched_pair()
        spectator, outsider = self.guest("spectator"), self.guest("outsider")
        spectator_socket, outsider_socket = self.connect(spectator), self.connect(outsider)
        spectator_socket.events.clear()
        outsider_socket.events.clear()
        run_async(self.arena.spectate(spectator.id, match_id, "watch"))
        state = spectator_socket.events[0]
        self.assertEqual(state["type"], "spectator_state")
        self.assertEqual({item["id"] for item in state["participants"]}, {first.id, second.id})
        run_async(self.arena.submit_throw(first.id, "rock", "secret"))
        self.assertNotIn("rock", json.dumps(spectator_socket.events))
        self.assertFalse(any(event["type"] == "spectator_state"
            for event in outsider_socket.events))
        run_async(self.arena.submit_throw(second.id, "rock", "reveal"))
        self.assertEqual(spectator_socket.events[-2]["type"], "round_reveal")
        self.assertEqual(spectator_socket.events[-2]["throws"][first.id], "rock")

    def test_spectator_reconnect_snapshot_contains_only_revealed_rounds(self) -> None:
        first, _, second, _, match_id = self.matched_pair()
        spectator = self.guest("spectator")
        original = self.connect(spectator)
        run_async(self.arena.spectate(spectator.id, match_id, "watch"))
        run_async(self.arena.submit_throw(first.id, "paper", "one"))
        run_async(self.arena.submit_throw(second.id, "paper", "two"))
        run_async(self.arena.disconnect(original))
        replacement = self.connect(self.repository.player(spectator.id))
        run_async(self.arena.spectate(spectator.id, match_id, "watch-again"))
        state = [event for event in replacement.events
            if event["type"] == "spectator_state"][-1]
        self.assertEqual(state["tie_count"], 1)
        self.assertEqual(len(state["revealed_rounds"]), 1)

    def test_completed_match_notifies_spectators_then_moves_to_recent_results(self) -> None:
        first, _, second, _, match_id = self.matched_pair()
        spectator = self.guest("spectator")
        socket = self.connect(spectator)
        run_async(self.arena.spectate(spectator.id, match_id, "watch"))
        run_async(self.arena.submit_throw(first.id, "rock", "one"))
        run_async(self.arena.submit_throw(second.id, "scissors", "two"))
        result = next(event for event in socket.events
            if event["type"] == "match_result")
        self.assertEqual(result["winner_id"], first.id)
        snapshot = [event for event in socket.events
            if event["type"] == "arena_snapshot"][-1]
        self.assertEqual(snapshot["active_matches"], 0)
        self.assertEqual(snapshot["top_matches"], [])
        self.assertEqual(snapshot["recent_results"][0]["match_id"], match_id)

    def test_leave_spectator_updates_count_and_stops_scoped_events(self) -> None:
        first, _, second, _, match_id = self.matched_pair()
        spectator = self.guest("spectator")
        socket = self.connect(spectator)
        run_async(self.arena.spectate(spectator.id, match_id, "watch"))
        run_async(self.arena.leave_spectator(spectator.id, match_id, "leave"))
        marker = len(socket.events)
        run_async(self.arena.submit_throw(first.id, "rock", "one"))
        run_async(self.arena.submit_throw(second.id, "rock", "two"))
        scoped = {"round_reveal", "spectator_state", "spectator_count"}
        self.assertFalse(any(event["type"] in scoped for event in socket.events[marker:]))


if __name__ == "__main__":
    unittest.main()
