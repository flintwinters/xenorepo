"""Normalized board state and reversible mutation history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from threading import Lock
from typing import Annotated, Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Integer, String,
    Text, UniqueConstraint, delete, inspect, select, update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from monotools.database import create_session_factory as _create_session_factory


CardTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
NoteBody = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]


class Column(BaseModel):
    id: str
    title: str


class Card(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    column_id: str
    reviewed_at_ms: int | None = None


class CardNote(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    card_id: str
    body: str
    created_at_ms: int


class Board(BaseModel):
    columns: list[Column]
    cards: list[Card]
    notes: list[CardNote]
    can_undo: bool
    can_redo: bool
    undo_description: str | None
    redo_description: str | None


class CardCreate(BaseModel):
    title: CardTitle
    column_id: str


class CardNoteCreate(BaseModel):
    body: NoteBody


class CardUpdate(BaseModel):
    title: CardTitle | None = None
    column_id: str | None = None
    index: int | None = None
    reviewed: bool | None = None

    @model_validator(mode="after")
    def require_update(self) -> CardUpdate:
        if (self.title is None and self.column_id is None and self.index is None
            and self.reviewed is None):
            raise ValueError("At least one card field must be updated")
        if self.index is not None and self.index < 0:
            raise ValueError("Destination index must be non-negative")
        return self


class BoardError(ValueError):
    def __init__(self, message: str, kind: str = "validation") -> None:
        super().__init__(message)
        self.kind = kind


class UnknownColumnError(BoardError):
    def __init__(self, column_id: str) -> None:
        super().__init__(f"Unknown column: {column_id}")


class InvalidPositionError(BoardError):
    def __init__(self, position: int) -> None:
        super().__init__(f"Invalid destination index: {position}")


class Base(DeclarativeBase):
    pass


class CardIdentity(Base):
    __tablename__ = "card_identities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)


class CardRecord(Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint("position >= 0", name="card_nonnegative_position"),
        UniqueConstraint("column_id", "position", name="card_column_position"),
    )
    id: Mapped[str] = mapped_column(
        String(36), ForeignKey("card_identities.id"), primary_key=True
    )
    title: Mapped[str] = mapped_column(String(120))
    column_id: Mapped[str] = mapped_column(String(40), index=True)
    position: Mapped[int] = mapped_column(Integer)
    reviewed_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class CardNoteRecord(Base):
    __tablename__ = "card_notes"
    __table_args__ = (
        Index("note_card_created", "card_id", "created_at_ms", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    card_id: Mapped[str] = mapped_column(
        ForeignKey("card_identities.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text)
    created_at_ms: Mapped[int] = mapped_column(BigInteger)


class Mutation(Base):
    __tablename__ = "mutations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str | None] = mapped_column(String(300))
    applied: Mapped[bool] = mapped_column(Boolean, index=True)


class MutationCard(Base):
    __tablename__ = "mutation_cards"
    __table_args__ = (
        CheckConstraint("phase IN ('before', 'after')", name="mutation_card_phase"),
        CheckConstraint("position >= 0", name="mutation_card_nonnegative_position"),
    )
    mutation_id: Mapped[int] = mapped_column(
        ForeignKey("mutations.id", ondelete="CASCADE"), primary_key=True
    )
    phase: Mapped[str] = mapped_column(String(6), primary_key=True)
    card_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("card_identities.id"), primary_key=True
    )
    title: Mapped[str] = mapped_column(String(120))
    column_id: Mapped[str] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(Integer)
    reviewed_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


_BROWSER_FIXTURE_TITLE = re.compile(
    r"^(?:Browser-validated card|First|Second|Renamed) \d{13}$"
)


def prepare_database(engine: Engine) -> None:
    """Apply additive schema migrations before repairing historical fixture data."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table in ("cards", "mutation_cards"):
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "reviewed_at_ms" not in columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN reviewed_at_ms BIGINT"
                )
        known_ids = connection.execute(select(CardIdentity.id)).scalars().all()
        card_ids = connection.execute(select(CardRecord.id)).scalars().all()
        historical_ids = connection.execute(select(MutationCard.card_id)).scalars().all()
        for card_id in set([*card_ids, *historical_ids]) - set(known_ids):
            connection.execute(CardIdentity.__table__.insert().values(id=card_id))
    remove_browser_fixture_contamination(engine)


def remove_browser_fixture_contamination(engine: Engine) -> None:
    """Remove historical UI-check fixtures written by the former server-env bug."""
    with engine.begin() as connection:
        current = connection.execute(select(CardRecord.id, CardRecord.title)).all()
        historical = connection.execute(
            select(MutationCard.card_id, MutationCard.title)
        ).all()
        contaminated = {
            identifier for identifier, title in [*current, *historical]
            if _BROWSER_FIXTURE_TITLE.fullmatch(title)
        }
        descriptions = connection.execute(select(Mutation.id, Mutation.description)).all()
        fixture_mutations = {
            identifier for identifier, description in descriptions
            if description and any(
                _BROWSER_FIXTURE_TITLE.fullmatch(candidate)
                for candidate in re.findall(r"“([^”]+)”", description)
            )
        }
        if fixture_mutations:
            connection.execute(delete(Mutation).where(Mutation.id.in_(fixture_mutations)))
        if contaminated:
            connection.execute(delete(CardRecord).where(CardRecord.id.in_(contaminated)))
            connection.execute(delete(MutationCard).where(
                MutationCard.card_id.in_(contaminated)))
        _compact_positions(connection, CardRecord.__table__, ())
        _compact_positions(connection, MutationCard.__table__,
            (MutationCard.mutation_id, MutationCard.phase))


def _compact_positions(connection, table, partition_columns: tuple) -> None:
    columns = [*partition_columns, table.c.column_id, table.c.position]
    identity = table.c.id if "id" in table.c else table.c.card_id
    rows = connection.execute(select(identity, *columns).order_by(
        *partition_columns, table.c.column_id, table.c.position)).all()
    counters: dict[tuple[object, ...], int] = {}
    for row in rows:
        values = tuple(row[index + 1] for index in range(len(partition_columns) + 1))
        position = counters.get(values, 0)
        counters[values] = position + 1
        conditions = [identity == row[0]]
        conditions.extend(column == row[index + 1]
            for index, column in enumerate(partition_columns))
        connection.execute(update(table).where(*conditions).values(position=position))


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    return _create_session_factory(database_url, Base.metadata)


@dataclass
class BoardStore:
    """Thread-safe authority for one fixed-column board."""

    sessions: sessionmaker[Session]
    columns: tuple[Column, ...] = (
        Column(id="todo", title="To do"),
        Column(id="doing", title="Doing"),
        Column(id="done", title="Done"),
    )
    now: Callable[[], datetime] = lambda: datetime.now(UTC)

    def __post_init__(self) -> None:
        self._lock = Lock()

    @classmethod
    def with_demo_cards(cls, sessions: sessionmaker[Session]) -> BoardStore:
        store = cls(sessions)
        with sessions() as session:
            persisted = session.scalar(select(CardRecord.id).limit(1)) is not None
            history = session.scalar(select(Mutation.id).limit(1)) is not None
        if not persisted and not history:
            store.create(CardCreate(title="Shape the walking skeleton", column_id="doing"))
            store.create(CardCreate(title="Ship the first useful slice", column_id="todo"))
        return store

    def snapshot(self) -> Board:
        with self._lock, self.sessions() as session:
            return self._snapshot(session)

    def create(self, request: CardCreate) -> Card:
        self._require_column(request.column_id)
        card = Card(id=str(uuid4()), title=request.title, column_id=request.column_id)
        with self._lock, self.sessions.begin() as session:
            before = self._cards(session)
            self._record(session, before, [*before, card], f'Create “{card.title}”')
        return card

    def update(self, card_id: str, request: CardUpdate) -> Card | None:
        if request.column_id is not None:
            self._require_column(request.column_id)
        with self._lock, self.sessions.begin() as session:
            before = self._cards(session)
            card = next((item for item in before if item.id == card_id), None)
            if card is None:
                return None
            updated, after, descriptions = self._apply_update(before, card, request)
            if descriptions:
                self._record(session, before, after, "; ".join(descriptions))
            return updated

    def append_note(self, card_id: str, request: CardNoteCreate) -> CardNote | None:
        with self._lock, self.sessions.begin() as session:
            if session.get(CardRecord, card_id) is None:
                return None
            note = CardNote(id=str(uuid4()), card_id=card_id, body=request.body,
                created_at_ms=int(self.now().timestamp() * 1000))
            session.add(CardNoteRecord(**note.model_dump()))
            return note

    def delete(self, card_id: str) -> bool:
        with self._lock, self.sessions.begin() as session:
            before = self._cards(session)
            after = [card for card in before if card.id != card_id]
            if len(after) == len(before):
                return False
            removed = next(card for card in before if card.id == card_id)
            self._record(session, before, after, f'Delete “{removed.title}”')
        return True

    def undo(self) -> Board | None:
        return self._shift_history(applied=True)

    def redo(self) -> Board | None:
        return self._shift_history(applied=False)

    def _shift_history(self, *, applied: bool) -> Board | None:
        ordering = Mutation.id.desc() if applied else Mutation.id.asc()
        with self._lock, self.sessions.begin() as session:
            mutation = session.scalar(
                select(Mutation).where(Mutation.applied == applied).order_by(ordering).limit(1)
            )
            if mutation is None:
                return None
            phase = "before" if applied else "after"
            cards = self._historical_cards(session, mutation.id, phase)
            self._replace_cards(session, cards)
            mutation.applied = not applied
            session.flush()
            return self._snapshot(session)

    def _apply_update(self, before: list[Card], card: Card, request: CardUpdate
        ) -> tuple[Card, list[Card], list[str]]:
        destination = request.column_id or card.column_id
        updated = card.model_copy(update={
            "title": request.title if request.title is not None else card.title,
            "column_id": destination,
            "reviewed_at_ms": (
                int(self.now().timestamp() * 1000) if request.reviewed is True
                else None if request.reviewed is False else card.reviewed_at_ms
            ),
        })
        remaining = [item for item in before if item.id != card.id]
        destination_cards = [item for item in remaining if item.column_id == destination]
        old_index = [item.id for item in before if item.column_id == card.column_id].index(card.id)
        reordering = request.column_id is not None or request.index is not None
        index = old_index if not reordering else (
            len(destination_cards) if request.index is None else request.index
        )
        if index > len(destination_cards):
            raise InvalidPositionError(index)
        insertion = len(remaining)
        if index < len(destination_cards):
            insertion = remaining.index(destination_cards[index])
        elif destination_cards:
            insertion = remaining.index(destination_cards[-1]) + 1
        after = [*remaining[:insertion], updated, *remaining[insertion:]]
        descriptions = self._describe_update(card, updated, destination, old_index, index, reordering)
        return updated, after, descriptions

    def _describe_update(self, card: Card, updated: Card, destination: str,
        old_index: int, index: int, reordering: bool) -> list[str]:
        descriptions: list[str] = []
        if updated.title != card.title:
            descriptions.append(f'Rename “{card.title}” to “{updated.title}”')
        if reordering and (destination != card.column_id or index != old_index):
            title = next(column.title for column in self.columns if column.id == destination)
            descriptions.append(f'Move “{updated.title}” to {title}')
        if updated.reviewed_at_ms != card.reviewed_at_ms:
            action = "Mark reviewed" if updated.reviewed_at_ms is not None else "Reset review"
            descriptions.append(f'{action} “{updated.title}”')
        return descriptions

    def _record(self, session: Session, before: list[Card], after: list[Card],
        description: str) -> None:
        session.execute(delete(Mutation).where(Mutation.applied.is_(False)))
        self._replace_cards(session, after)
        mutation = Mutation(description=description, applied=True)
        session.add(mutation)
        session.flush()
        self._add_history(session, mutation.id, "before", before)
        self._add_history(session, mutation.id, "after", after)

    def _snapshot(self, session: Session) -> Board:
        undo = session.scalar(
            select(Mutation).where(Mutation.applied.is_(True)).order_by(Mutation.id.desc()).limit(1)
        )
        redo = session.scalar(
            select(Mutation).where(Mutation.applied.is_(False)).order_by(Mutation.id.asc()).limit(1)
        )
        cards = self._cards(session)
        card_ids = [card.id for card in cards]
        notes = [] if not card_ids else session.scalars(select(CardNoteRecord).where(
            CardNoteRecord.card_id.in_(card_ids)).order_by(
                CardNoteRecord.created_at_ms, CardNoteRecord.id)).all()
        return Board(columns=list(self.columns), cards=cards,
            notes=[CardNote.model_validate(note) for note in notes],
            can_undo=undo is not None, can_redo=redo is not None,
            undo_description=(undo.description or "Update board") if undo else None,
            redo_description=(redo.description or "Update board") if redo else None)

    def _cards(self, session: Session) -> list[Card]:
        records = session.scalars(select(CardRecord)).all()
        column_order = {column.id: index for index, column in enumerate(self.columns)}
        records.sort(key=lambda row: (column_order[row.column_id], row.position))
        return [Card.model_validate(row) for row in records]

    def _historical_cards(self, session: Session, mutation_id: int, phase: str) -> list[Card]:
        rows = session.scalars(select(MutationCard).where(
            MutationCard.mutation_id == mutation_id, MutationCard.phase == phase
        ).order_by(MutationCard.position)).all()
        return [Card(id=row.card_id, title=row.title, column_id=row.column_id,
            reviewed_at_ms=row.reviewed_at_ms) for row in rows]

    def _replace_cards(self, session: Session, cards: list[Card]) -> None:
        session.execute(delete(CardRecord))
        positions = {column.id: 0 for column in self.columns}
        for card in cards:
            if session.get(CardIdentity, card.id) is None:
                session.add(CardIdentity(id=card.id))
                session.flush()
            session.add(CardRecord(id=card.id, title=card.title, column_id=card.column_id,
                position=positions[card.column_id], reviewed_at_ms=card.reviewed_at_ms))
            positions[card.column_id] += 1
        session.flush()

    def _add_history(self, session: Session, mutation_id: int, phase: str,
        cards: list[Card]) -> None:
        positions = {column.id: 0 for column in self.columns}
        for card in cards:
            session.add(MutationCard(mutation_id=mutation_id, phase=phase, card_id=card.id,
                title=card.title, column_id=card.column_id, position=positions[card.column_id],
                reviewed_at_ms=card.reviewed_at_ms))
            positions[card.column_id] += 1

    def _require_column(self, column_id: str) -> None:
        if not any(column.id == column_id for column in self.columns):
            raise UnknownColumnError(column_id)
