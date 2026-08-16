"""Single-process live arena coordination over durable domain transitions."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from apps.rps.database import DomainError, Player, RpsRepository
from apps.rps.scheduling import Clock, Scheduler
from tooling.realtime import ConnectionRegistry, RealtimeSocket, SendReport, client_provenance


ROUND_TIME = timedelta(seconds=10)
RECONNECT_TIME = timedelta(seconds=5)
POST_MATCH_PAUSE = timedelta(milliseconds=200)


def permitted_streak_difference(waited_seconds: float) -> int | None:
    """Return the inclusive streak gap, or None once matching is unrestricted."""
    if waited_seconds >= 30:
        return None
    return max(0, int(waited_seconds // 5))


@dataclass(frozen=True)
class ArenaContext:
    player_id: str
    connection_id: str
    subscriptions: set[str] = field(default_factory=set, compare=False)


@dataclass(frozen=True)
class QueueRecord:
    player_id: str
    entry_id: str
    streak: int
    joined_at: datetime


@dataclass
class LiveMatch:
    id: str
    players: tuple[str, str]
    round_number: int
    deadline: datetime
    submitted: set[str] = field(default_factory=set)
    disconnected: dict[str, datetime] = field(default_factory=dict)
    ranked: bool = True
    streaks: tuple[int, int] = (0, 0)
    started_at: datetime | None = None
    reveals: list[dict[str, object]] = field(default_factory=list)


class ArenaCoordinator:
    """Serialize ephemeral arena policy around committed repository transitions."""

    def __init__(self, repository: RpsRepository, clock: Clock, scheduler: Scheduler) -> None:
        self.repository = repository
        self.clock = clock
        self.scheduler = scheduler
        self.connections = ConnectionRegistry[ArenaContext]()
        self.queue: dict[str, QueueRecord] = {}
        self.matches: dict[str, LiveMatch] = {}
        self.player_matches: dict[str, str] = {}
        self.mutations: set[tuple[str, str]] = set()
        self.recent_results: list[dict[str, object]] = []

    async def connect(self, socket: RealtimeSocket, player: Player) -> None:
        await socket.accept()  # type: ignore[attr-defined]
        connection_id = self.repository.open_connection(player.id, client_provenance(socket))
        self.connections.register(socket, ArenaContext(player.id, connection_id))
        match = self._player_match(player.id)
        if match and player.id in match.disconnected:
            match.disconnected.pop(player.id)
            self.repository.set_connection_state(match.id, player.id, None)
        await self._send_player(player.id, {"type": "session", "player": self._player(player.id)})
        if player.id in self.queue:
            await self._send_player(player.id, {"type": "queue_state", "queued": True})
        if match:
            await self._send_match_snapshot(player.id, match)
        await self._broadcast_arena()

    async def disconnect(self, socket: RealtimeSocket) -> None:
        context = self.connections.remove(socket)
        if context:
            await self._connection_lost(context)
        await self._broadcast_arena()

    async def join_queue(self, player_id: str, client_id: str) -> None:
        if not self._claim_mutation(player_id, client_id):
            return
        if player_id in self.player_matches:
            raise DomainError("Player is already in a match.")
        if player_id in self.queue:
            return
        await self._queue_player(player_id)

    async def _queue_player(self, player_id: str) -> None:
        """Create one durable queue entry and immediately seek an opponent."""
        entry = self.repository.join_queue(player_id)
        player = self.repository.player(player_id)
        record = QueueRecord(player_id, entry.id, player.competitive_streak, self.clock.now())
        self.queue[player_id] = record
        await self._broadcast_arena()
        await self._send_player(player_id, {"type": "queue_state", "queued": True})
        self._schedule_queue_checks(record)
        await self.attempt_matches()

    async def _requeue_completed_player(self, player_id: str) -> None:
        """Return a completed player to matchmaking unless their state changed."""
        if player_id in self.player_matches or player_id in self.queue:
            return
        await self._queue_player(player_id)

    async def _requeue_completed_players(self, player_ids: tuple[str, str]) -> None:
        """Return both participants through one ordered post-match handoff."""
        for player_id in player_ids:
            await self._requeue_completed_player(player_id)

    async def leave_queue(self, player_id: str, client_id: str) -> None:
        if not self._claim_mutation(player_id, client_id):
            return
        record = self.queue.pop(player_id, None)
        if record is None:
            raise DomainError("Player is not queued.")
        self.repository.leave_queue(record.entry_id)
        await self._broadcast_arena()
        await self._send_player(player_id, {"type": "queue_state", "queued": False})

    async def spectate(self, player_id: str, match_id: str, client_id: str) -> None:
        if not self._claim_mutation(player_id, client_id):
            return
        match = self.matches.get(match_id)
        if match is None:
            raise DomainError("Match is not available for spectating.")
        for socket, context in self.connections.connections():
            if context.player_id == player_id:
                context.subscriptions.add(match_id)
                await self.connections.send(socket, self._spectator_state(match))
        await self._broadcast_spectator_count(match_id)

    async def leave_spectator(self, player_id: str, match_id: str, client_id: str) -> None:
        if not self._claim_mutation(player_id, client_id):
            return
        changed = False
        for _, context in self.connections.connections():
            if context.player_id == player_id and match_id in context.subscriptions:
                context.subscriptions.remove(match_id)
                changed = True
        if not changed:
            raise DomainError("Player is not spectating this match.")
        await self._broadcast_spectator_count(match_id)

    async def attempt_matches(self) -> None:
        while True:
            pair = self._best_pair()
            if pair is None:
                return
            first, second = pair
            deadline = self.clock.now() + ROUND_TIME
            match = self.repository.create_match(first.player_id, second.player_id,
                selection_deadline_at=deadline,
                queue_entry_ids=(first.entry_id, second.entry_id))
            self.queue.pop(first.player_id, None)
            self.queue.pop(second.player_id, None)
            live = LiveMatch(match.id, (first.player_id, second.player_id), 1, deadline,
                ranked=match.ranked, streaks=(first.streak, second.streak),
                started_at=match.started_at)
            self.matches[match.id] = live
            self.player_matches[first.player_id] = match.id
            self.player_matches[second.player_id] = match.id
            self._schedule_round(live)
            await self._announce_match(live)
            await self._broadcast_arena()

    async def submit_throw(self, player_id: str, selection: str, client_id: str) -> None:
        if not self._claim_mutation(player_id, client_id):
            return
        match = self._player_match(player_id)
        if match is None:
            raise DomainError("Player is not in an active match.")
        if self.clock.now() >= match.deadline:
            await self._expire_round(match.id, match.round_number)
            raise DomainError("Round deadline has passed.")
        next_deadline = self.clock.now() + ROUND_TIME
        result = self.repository.submit_throw(match.id, player_id, selection, next_deadline)
        match.submitted.add(player_id)
        if result["state"] == "concealed":
            await self._broadcast_round_state(match)
            return
        await self._reveal(match, result)
        if result["state"] == "completed":
            await self._finish(match, result)
            return
        match.round_number += 1
        match.deadline = next_deadline
        match.submitted.clear()
        self._schedule_round(match)
        await self._broadcast_round_state(match)

    async def _expire_round(self, match_id: str, round_number: int) -> None:
        match = self.matches.get(match_id)
        if match is None or match.round_number != round_number:
            return
        timestamp = self.clock.now()
        if timestamp < match.deadline:
            return
        missing = set(match.players) - match.submitted
        grace = [deadline for player_id, deadline in match.disconnected.items()
            if player_id in missing and deadline > timestamp]
        if grace:
            self.scheduler.call_at(max(grace),
                lambda: self._expire_round(match_id, round_number))
            return
        await self._fail(match, missing)

    async def _expire_reconnect(self, match_id: str, player_id: str,
        deadline: datetime) -> None:
        match = self.matches.get(match_id)
        if match is None or match.disconnected.get(player_id) != deadline:
            return
        if self.clock.now() < deadline:
            return
        failed = {candidate for candidate, due in match.disconnected.items()
            if due <= self.clock.now()}
        await self._fail(match, failed)

    async def _fail(self, match: LiveMatch, failed: set[str]) -> None:
        if not failed:
            return
        result = self.repository.fail_match(match.id, failed)
        await self._finish(match, result)

    async def _finish(self, match: LiveMatch, result: dict[str, object]) -> None:
        public_result = {"match_id": match.id, "ranked": match.ranked,
            "participants": [self._player(player_id) for player_id in match.players],
            "outcome": result["outcome"], "winner_id": result.get("winner_id"),
            "completed_at": self.clock.now().isoformat()}
        self.recent_results.insert(0, public_result)
        del self.recent_results[10:]
        self.matches.pop(match.id, None)
        for player_id in match.players:
            self.player_matches.pop(player_id, None)
        await self._broadcast_arena()
        for player_id in match.players:
            await self._send_player(player_id, {"type": "match_result", **result,
                "player": self._player(player_id)})
        await self._send_spectators(match.id, {"type": "match_result", **public_result})
        for _, context in self.connections.connections():
            context.subscriptions.discard(match.id)
        self.scheduler.call_at(self.clock.now() + POST_MATCH_PAUSE,
            lambda: self._requeue_completed_players(match.players))

    async def _reveal(self, match: LiveMatch, result: dict[str, object]) -> None:
        outcome = "tie" if result["state"] == "active" else "decisive"
        event = {"type": "round_reveal", "match_id": match.id,
            "round": result["round"], "throws": result["throws"],
            "outcome": outcome, "winner_id": result.get("winner_id")}
        match.reveals.append(event)
        await self._send_match(match, event)
        await self._send_spectators(match.id, event)

    async def _announce_match(self, match: LiveMatch) -> None:
        for player_id in match.players:
            opponent_id = next(candidate for candidate in match.players if candidate != player_id)
            await self._send_player(player_id, {"type": "match_assignment",
                "match_id": match.id, "ranked": True, "opponent": self._player(opponent_id)})
        await self._broadcast_round_state(match)

    async def _send_match_snapshot(self, player_id: str, match: LiveMatch) -> None:
        opponent_id = next(candidate for candidate in match.players if candidate != player_id)
        await self._send_player(player_id, {"type": "match_assignment", "match_id": match.id,
            "ranked": True, "opponent": self._player(opponent_id)})
        await self._send_player(player_id, self._round_state(match, player_id))

    async def _broadcast_round_state(self, match: LiveMatch) -> None:
        for player_id in match.players:
            await self._send_player(player_id, self._round_state(match, player_id))
        await self._send_spectators(match.id, self._spectator_state(match))

    def _round_state(self, match: LiveMatch, player_id: str) -> dict[str, object]:
        opponent_id = next(candidate for candidate in match.players if candidate != player_id)
        return {"type": "round_state", "match_id": match.id,
            "round": match.round_number, "deadline": match.deadline.isoformat(),
            "submitted": player_id in match.submitted,
            "opponent_submitted": opponent_id in match.submitted}

    async def _send_match(self, match: LiveMatch, event: dict[str, Any]) -> None:
        report = await self.connections.broadcast(event,
            lambda context: context.player_id in match.players)
        await self._clean_stale(report)

    async def _send_player(self, player_id: str, event: dict[str, Any]) -> None:
        report = await self.connections.broadcast(event,
            lambda context: context.player_id == player_id)
        await self._clean_stale(report)

    async def _broadcast_arena(self) -> None:
        players = {context.player_id for _, context in self.connections.connections()}
        event = {"type": "arena_snapshot", "visitors": len(players),
            "queue_size": len(self.queue), "active_matches": len(self.matches),
            "top_matches": [self._match_listing(match) for match in self._ranked_matches()],
            "recent_results": self.recent_results}
        report = await self.connections.broadcast(event)
        await self._clean_stale(report)

    async def _send_spectators(self, match_id: str, event: dict[str, Any]) -> None:
        report = await self.connections.broadcast(event,
            lambda context: match_id in context.subscriptions)
        await self._clean_stale(report)

    async def _broadcast_spectator_count(self, match_id: str) -> None:
        match = self.matches.get(match_id)
        if match is None:
            return
        await self._send_spectators(match_id, {"type": "spectator_count",
            "match_id": match_id, "count": self._spectator_count(match_id)})
        await self._broadcast_arena()

    def _spectator_count(self, match_id: str) -> int:
        return len({context.player_id for _, context in self.connections.connections()
            if match_id in context.subscriptions})

    def _spectator_state(self, match: LiveMatch) -> dict[str, object]:
        return {"type": "spectator_state", "match_id": match.id,
            "ranked": match.ranked, "participants": [self._player(player_id)
                for player_id in match.players], "round": match.round_number,
            "deadline": match.deadline.isoformat(), "tie_count": sum(
                reveal["outcome"] == "tie" for reveal in match.reveals),
            "revealed_rounds": match.reveals, "spectator_count": self._spectator_count(match.id)}

    def _ranked_matches(self) -> list[LiveMatch]:
        return sorted(self.matches.values(), key=lambda match: (
            -max(match.streaks), -sum(match.streaks), match.started_at or self.clock.now(), match.id))

    def _match_listing(self, match: LiveMatch) -> dict[str, object]:
        return {"match_id": match.id, "ranked": match.ranked,
            "participants": [self._player(player_id) for player_id in match.players],
            "highest_streak": max(match.streaks), "combined_streak": sum(match.streaks),
            "started_at": match.started_at.isoformat() if match.started_at else None,
            "spectator_count": self._spectator_count(match.id)}

    async def _clean_stale(self, report: SendReport[ArenaContext]) -> None:
        for disconnected in report.disconnected:
            await self._connection_lost(disconnected.context)

    async def _connection_lost(self, context: ArenaContext) -> None:
        try:
            self.repository.close_connection(context.connection_id)
        except DomainError:
            pass
        if any(candidate.player_id == context.player_id
            for _, candidate in self.connections.connections()):
            return
        record = self.queue.pop(context.player_id, None)
        if record:
            self.repository.leave_queue(record.entry_id)
            await self._broadcast_arena()
        match = self._player_match(context.player_id)
        if match:
            deadline = self.clock.now() + RECONNECT_TIME
            match.disconnected[context.player_id] = deadline
            self.repository.set_connection_state(match.id, context.player_id, deadline)
            self.scheduler.call_at(deadline,
                lambda: self._expire_reconnect(match.id, context.player_id, deadline))

    def _best_pair(self) -> tuple[QueueRecord, QueueRecord] | None:
        records = sorted(self.queue.values(), key=lambda item: (item.joined_at, item.entry_id))
        candidates: list[tuple[tuple[object, ...], QueueRecord, QueueRecord]] = []
        for index, first in enumerate(records):
            for second in records[index + 1:]:
                difference = abs(first.streak - second.streak)
                waited = (self.clock.now() - first.joined_at).total_seconds()
                allowed = permitted_streak_difference(waited)
                if allowed is None or difference <= allowed:
                    candidates.append(((difference, first.joined_at, second.joined_at,
                        first.entry_id, second.entry_id), first, second))
        return min(candidates, key=lambda item: item[0])[1:] if candidates else None

    def _schedule_queue_checks(self, record: QueueRecord) -> None:
        for seconds in range(5, 31, 5):
            self.scheduler.call_at(record.joined_at + timedelta(seconds=seconds),
                self.attempt_matches)

    def _schedule_round(self, match: LiveMatch) -> None:
        match_id, round_number = match.id, match.round_number
        self.scheduler.call_at(match.deadline,
            lambda: self._expire_round(match_id, round_number))

    def _player_match(self, player_id: str) -> LiveMatch | None:
        match_id = self.player_matches.get(player_id)
        return self.matches.get(match_id) if match_id else None

    def _player(self, player_id: str) -> dict[str, object]:
        player = self.repository.player(player_id)
        return {"id": player.id, "nickname": player.nickname,
            "competitive_streak": player.competitive_streak}

    def _claim_mutation(self, player_id: str, client_id: str) -> bool:
        if not 1 <= len(client_id) <= 64:
            raise DomainError("Client mutation ID is required.")
        key = (player_id, client_id)
        if key in self.mutations:
            return False
        self.mutations.add(key)
        return True
