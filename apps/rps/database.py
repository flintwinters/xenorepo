"""Durable competitive domain for Rock Paper Scissors."""

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    select,
    inspect,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from apps.rps.auth import credential_digest
from monotools.database import ClientProvenanceMixin
from monotools.appkit import SystemClock
from monotools.database import create_session_factory as _create_session_factory


THROWS = frozenset({"rock", "paper", "scissors"})
now = SystemClock().now


class DomainError(ValueError):
    """A stable rejection of an illegal competitive-domain operation."""


class Base(DeclarativeBase):
    pass


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    """Compatibility factory for tests and standalone app-domain consumers."""
    return _create_session_factory(database_url, Base.metadata, _migrate_realtime_columns)


class Player(Base):
    __tablename__ = "players"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(24), index=True)
    competitive_streak: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("competitive_streak >= 0", name="nonnegative_streak"),)


class GuestCredential(Base):
    __tablename__ = "guest_credentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), unique=True, index=True)
    digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConnectionSession(ClientProvenanceMixin, Base):
    __tablename__ = "connection_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), index=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ranked: Mapped[bool] = mapped_column(Boolean, index=True)
    state: Mapped[str] = mapped_column(String(16), index=True)
    outcome: Mapped[str | None] = mapped_column(String(16))
    winner_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"), index=True)
    loser_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rematch_of_id: Mapped[str | None] = mapped_column(ForeignKey("matches.id"))
    __table_args__ = (
        CheckConstraint("state IN ('active', 'completed')", name="match_state"),
        CheckConstraint("outcome IS NULL OR outcome IN ('decisive', 'draw', 'forfeit')",
            name="match_outcome"),
        CheckConstraint("winner_id IS NULL OR winner_id <> loser_id", name="distinct_result_players"),
        CheckConstraint("(state = 'active' AND outcome IS NULL AND completed_at IS NULL "
            "AND winner_id IS NULL AND loser_id IS NULL) OR "
            "(state = 'completed' AND outcome IS NOT NULL AND completed_at IS NOT NULL)",
            name="match_completion_shape"),
        CheckConstraint("outcome IS NULL OR (outcome = 'draw' AND winner_id IS NULL "
            "AND loser_id IS NULL) OR (outcome IN ('decisive', 'forfeit') "
            "AND winner_id IS NOT NULL AND loser_id IS NOT NULL)", name="match_result_shape"),
    )


class MatchParticipant(Base):
    __tablename__ = "match_participants"
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), primary_key=True)
    seat: Mapped[int] = mapped_column(Integer)
    streak_at_start: Mapped[int] = mapped_column(Integer)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconnect_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("match_id", "seat"),
        CheckConstraint("seat IN (1, 2)", name="participant_seat"),
        CheckConstraint("streak_at_start >= 0", name="participant_streak"),
    )


class Round(Base):
    __tablename__ = "rounds"
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str | None] = mapped_column(String(16))
    winner_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selection_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("number BETWEEN 1 AND 5", name="round_number"),
        CheckConstraint("state IN ('collecting', 'resolved', 'cancelled')", name="round_state"),
        CheckConstraint("outcome IS NULL OR outcome IN ('tie', 'decisive')", name="round_outcome"),
        CheckConstraint("(state = 'collecting' AND outcome IS NULL AND resolved_at IS NULL) OR "
            "(state = 'resolved' AND outcome IS NOT NULL AND resolved_at IS NOT NULL) OR "
            "(state = 'cancelled' AND outcome IS NULL AND resolved_at IS NOT NULL)",
            name="round_completion_shape"),
        CheckConstraint("outcome IS NULL OR (outcome = 'tie' AND winner_id IS NULL) OR "
            "(outcome = 'decisive' AND winner_id IS NOT NULL)", name="round_result_shape"),
    )


class Throw(Base):
    __tablename__ = "throws"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[str] = mapped_column(String(36))
    round_number: Mapped[int] = mapped_column(Integer)
    player_id: Mapped[str] = mapped_column(String(36))
    selection: Mapped[str] = mapped_column(String(8))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["match_id", "round_number"], ["rounds.match_id", "rounds.number"]),
        ForeignKeyConstraint(["match_id", "player_id"],
            ["match_participants.match_id", "match_participants.player_id"]),
        UniqueConstraint("match_id", "round_number", "player_id"),
        CheckConstraint("selection IN ('rock', 'paper', 'scissors')", name="throw_selection"),
    )


class MatchmakingEntry(Base):
    __tablename__ = "matchmaking_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), index=True)
    state: Mapped[str] = mapped_column(String(12), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    match_id: Mapped[str | None] = mapped_column(ForeignKey("matches.id"), index=True)
    __table_args__ = (CheckConstraint("state IN ('queued', 'left', 'matched')", name="queue_state"),)


def throw_result(first: str, second: str) -> int:
    """Return 1 when first wins, -1 when second wins, and 0 for a tie."""
    if first not in THROWS or second not in THROWS:
        raise ValueError("Throw must be rock, paper, or scissors.")
    if first == second:
        return 0
    return 1 if (first, second) in {
        ("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")
    } else -1


def _migrate_realtime_columns(engine: Engine) -> None:
    """Add checkpoint-three facts to databases created by the durable-domain release."""
    additions = {
        "match_participants": {
            "disconnected_at": "DATETIME",
            "reconnect_deadline_at": "DATETIME",
        },
        "rounds": {"selection_deadline_at": "DATETIME"},
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            existing = {column["name"] for column in inspect(connection).get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")


class RpsRepository:
    def __init__(self, sessions: sessionmaker[Session],
        clock: Callable[[], datetime] | None = None) -> None:
        self.sessions = sessions
        self.clock = clock or SystemClock().now

    def create_guest(self, raw_credential: str) -> Player:
        timestamp, player_id = self.clock(), str(uuid4())
        player = Player(id=player_id, nickname=f"Guest-{player_id[:4].upper()}",
            competitive_streak=0, created_at=timestamp, last_seen_at=timestamp)
        with self.sessions.begin() as session:
            session.add(player)
            session.flush()
            session.add(GuestCredential(id=str(uuid4()), player_id=player.id,
                digest=credential_digest(raw_credential), issued_at=timestamp))
        return player

    def restore_guest(self, raw_credential: str | None) -> Player | None:
        if not raw_credential:
            return None
        with self.sessions.begin() as session:
            player = session.scalar(select(Player).join(GuestCredential).where(
                GuestCredential.digest == credential_digest(raw_credential)))
            if player is not None:
                player.last_seen_at = self.clock()
            return player

    def rename(self, player_id: str, nickname: str) -> Player:
        cleaned = nickname.strip()
        if not 2 <= len(cleaned) <= 24:
            raise DomainError("Nickname must contain 2–24 characters.")
        with self.sessions.begin() as session:
            player = self._player(session, player_id)
            player.nickname = cleaned
            player.last_seen_at = self.clock()
            return player

    def open_connection(self, player_id: str, provenance: dict[str, str | None]) -> str:
        identifier = str(uuid4())
        with self.sessions.begin() as session:
            self._player(session, player_id)
            session.add(ConnectionSession(id=identifier, player_id=player_id,
                connected_at=self.clock(), disconnected_at=None, **provenance))
        return identifier

    def close_connection(self, connection_id: str) -> None:
        with self.sessions.begin() as session:
            connection = session.get(ConnectionSession, connection_id)
            if connection is None or connection.disconnected_at is not None:
                raise DomainError("Connection is not active.")
            connection.disconnected_at = self.clock()

    def join_queue(self, player_id: str) -> MatchmakingEntry:
        with self.sessions.begin() as session:
            self._player(session, player_id)
            active = session.scalar(select(MatchmakingEntry).where(
                MatchmakingEntry.player_id == player_id, MatchmakingEntry.state == "queued"))
            if active:
                raise DomainError("Player is already queued.")
            entry = MatchmakingEntry(id=str(uuid4()), player_id=player_id, state="queued",
                joined_at=self.clock(), left_at=None, match_id=None)
            session.add(entry)
            return entry

    def leave_queue(self, entry_id: str) -> None:
        with self.sessions.begin() as session:
            entry = session.get(MatchmakingEntry, entry_id)
            if entry is None or entry.state != "queued":
                raise DomainError("Queue entry is not active.")
            entry.state, entry.left_at = "left", self.clock()

    def create_match(self, first_id: str, second_id: str, *, ranked: bool = True,
        rematch_of_id: str | None = None, selection_deadline_at: datetime | None = None,
        queue_entry_ids: tuple[str, str] | None = None) -> Match:
        if first_id == second_id:
            raise DomainError("A match requires two distinct players.")
        timestamp, identifier = self.clock(), str(uuid4())
        with self.sessions.begin() as session:
            players = [self._player(session, player_id) for player_id in (first_id, second_id)]
            if rematch_of_id is not None:
                if ranked:
                    raise DomainError("Rematches must be unranked.")
                if session.get(Match, rematch_of_id) is None:
                    raise DomainError("Original match not found.")
            match = Match(id=identifier, ranked=ranked, state="active", outcome=None,
                winner_id=None, loser_id=None, started_at=timestamp, completed_at=None,
                rematch_of_id=rematch_of_id)
            session.add(match)
            session.add_all(MatchParticipant(match_id=identifier, player_id=player.id,
                seat=seat, streak_at_start=player.competitive_streak,
                disconnected_at=None, reconnect_deadline_at=None)
                for seat, player in enumerate(players, 1))
            session.add(Round(match_id=identifier, number=1, state="collecting",
                outcome=None, winner_id=None, started_at=timestamp, resolved_at=None))
            if selection_deadline_at is not None:
                session.flush()
                session.get(Round, (identifier, 1)).selection_deadline_at = selection_deadline_at
            if queue_entry_ids is not None:
                entries = [session.get(MatchmakingEntry, entry_id) for entry_id in queue_entry_ids]
                if any(entry is None or entry.state != "queued" for entry in entries):
                    raise DomainError("Queue entry is not active.")
                if {entry.player_id for entry in entries} != {first_id, second_id}:
                    raise DomainError("Queue entries do not match participants.")
                for entry in entries:
                    entry.state, entry.left_at, entry.match_id = "matched", timestamp, identifier
            session.flush()
            return match

    def submit_throw(self, match_id: str, player_id: str, selection: str,
        next_deadline_at: datetime | None = None) -> dict[str, object]:
        if selection not in THROWS:
            raise DomainError("Throw must be rock, paper, or scissors.")
        with self.sessions.begin() as session:
            match = self._active_match(session, match_id)
            participants = self._participants(session, match_id)
            if player_id not in participants:
                raise DomainError("Player is not a participant in this match.")
            round_ = session.scalar(select(Round).where(Round.match_id == match_id,
                Round.state == "collecting").with_for_update())
            if round_ is None:
                raise DomainError("Match has no active round.")
            duplicate = session.scalar(select(Throw).where(Throw.match_id == match_id,
                Throw.round_number == round_.number, Throw.player_id == player_id))
            if duplicate:
                raise DomainError("Player has already thrown in this round.")
            session.add(Throw(match_id=match_id, round_number=round_.number,
                player_id=player_id, selection=selection, submitted_at=self.clock()))
            session.flush()
            throws = session.scalars(select(Throw).where(Throw.match_id == match_id,
                Throw.round_number == round_.number)).all()
            if len(throws) == 1:
                return {"match_id": match_id, "round": round_.number, "state": "concealed"}
            return self._resolve_round(session, match, round_, participants, throws,
                next_deadline_at)

    def forfeit(self, match_id: str, loser_id: str) -> dict[str, object]:
        with self.sessions.begin() as session:
            match = self._active_match(session, match_id)
            participants = self._participants(session, match_id)
            if loser_id not in participants:
                raise DomainError("Player is not a participant in this match.")
            winner_id = next(player_id for player_id in participants if player_id != loser_id)
            round_ = session.scalar(select(Round).where(Round.match_id == match_id,
                Round.state == "collecting"))
            if round_ is not None:
                round_.state, round_.resolved_at = "cancelled", self.clock()
            self._complete_match(session, match, "forfeit", winner_id, loser_id)
            return self._match_state(match)

    def fail_match(self, match_id: str, failed_player_ids: set[str]) -> dict[str, object]:
        """Resolve one failure as a forfeit and simultaneous failures as a draw."""
        with self.sessions.begin() as session:
            match = self._active_match(session, match_id)
            participants = self._participants(session, match_id)
            if not failed_player_ids or not failed_player_ids <= participants.keys():
                raise DomainError("Failed players must be match participants.")
            round_ = session.scalar(select(Round).where(Round.match_id == match_id,
                Round.state == "collecting"))
            if round_ is not None:
                round_.state, round_.resolved_at = "cancelled", self.clock()
            if len(failed_player_ids) == 2:
                self._complete_match(session, match, "draw", None, None)
            else:
                loser_id = next(iter(failed_player_ids))
                winner_id = next(player_id for player_id in participants if player_id != loser_id)
                self._complete_match(session, match, "forfeit", winner_id, loser_id)
            return self._match_state(match)

    def set_connection_state(self, match_id: str, player_id: str,
        reconnect_deadline_at: datetime | None) -> None:
        with self.sessions.begin() as session:
            participant = session.get(MatchParticipant, (match_id, player_id))
            if participant is None:
                raise DomainError("Player is not a participant in this match.")
            participant.disconnected_at = self.clock() if reconnect_deadline_at else None
            participant.reconnect_deadline_at = reconnect_deadline_at

    def player(self, player_id: str) -> Player:
        with self.sessions() as session:
            return self._player(session, player_id)

    def match_state(self, match_id: str) -> dict[str, object]:
        with self.sessions() as session:
            match = session.get(Match, match_id)
            if match is None:
                raise DomainError("Match not found.")
            state = self._match_state(match)
            state["rounds"] = [{"number": round_.number, "state": round_.state,
                "outcome": round_.outcome, "winner_id": round_.winner_id}
                for round_ in session.scalars(select(Round).where(
                    Round.match_id == match_id).order_by(Round.number))]
            return state

    def _resolve_round(self, session: Session, match: Match, round_: Round,
        participants: dict[str, MatchParticipant], throws: list[Throw],
        next_deadline_at: datetime | None) -> dict[str, object]:
        ordered = sorted(throws, key=lambda item: participants[item.player_id].seat)
        result, timestamp = throw_result(ordered[0].selection, ordered[1].selection), self.clock()
        round_.state, round_.resolved_at = "resolved", timestamp
        if result == 0:
            round_.outcome = "tie"
            if round_.number == 5:
                self._complete_match(session, match, "draw", None, None)
            else:
                session.add(Round(match_id=match.id, number=round_.number + 1,
                    state="collecting", outcome=None, winner_id=None,
                    started_at=timestamp, resolved_at=None,
                    selection_deadline_at=next_deadline_at))
        else:
            winner = ordered[0].player_id if result == 1 else ordered[1].player_id
            loser = ordered[1].player_id if result == 1 else ordered[0].player_id
            round_.outcome, round_.winner_id = "decisive", winner
            self._complete_match(session, match, "decisive", winner, loser)
        state = self._match_state(match)
        state.update({"round": round_.number, "throws": {
            item.player_id: item.selection for item in throws}})
        return state

    def _complete_match(self, session: Session, match: Match, outcome: str,
        winner_id: str | None, loser_id: str | None) -> None:
        match.state, match.outcome, match.completed_at = "completed", outcome, self.clock()
        match.winner_id, match.loser_id = winner_id, loser_id
        if match.ranked and winner_id and loser_id:
            self._player(session, winner_id).competitive_streak += 1
            self._player(session, loser_id).competitive_streak = 0

    @staticmethod
    def _match_state(match: Match) -> dict[str, object]:
        return {"id": match.id, "ranked": match.ranked, "state": match.state,
            "outcome": match.outcome, "winner_id": match.winner_id,
            "loser_id": match.loser_id}

    @staticmethod
    def _player(session: Session, player_id: str) -> Player:
        player = session.get(Player, player_id)
        if player is None:
            raise DomainError("Player not found.")
        return player

    @staticmethod
    def _active_match(session: Session, match_id: str) -> Match:
        match = session.get(Match, match_id, with_for_update=True)
        if match is None:
            raise DomainError("Match not found.")
        if match.state != "active":
            raise DomainError("Match is already complete.")
        return match

    @staticmethod
    def _participants(session: Session, match_id: str) -> dict[str, MatchParticipant]:
        participants = session.scalars(select(MatchParticipant).where(
            MatchParticipant.match_id == match_id)).all()
        return {participant.player_id: participant for participant in participants}
