"""Durable single-board domain model and transactional operations."""

from datetime import UTC, datetime
from typing import Annotated, Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class KanbanError(ValueError):
    def __init__(self, message: str, kind: str = "validation") -> None:
        super().__init__(message)
        self.kind = kind


class ColumnCreate(BaseModel):
    name: Name


class ColumnUpdate(BaseModel):
    name: Name | None = None
    position: int | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ColumnUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one column field must be updated")
        if self.position is not None and self.position < 0:
            raise ValueError("position must not be negative")
        return self


class CardCreate(BaseModel):
    column_id: str
    title: Title
    description: Description = ""


class CardUpdate(BaseModel):
    title: Title | None = None
    description: Description | None = None
    column_id: str | None = None
    position: int | None = None

    @model_validator(mode="after")
    def require_change(self) -> "CardUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one card field must be updated")
        if self.position is not None and self.position < 0:
            raise ValueError("position must not be negative")
        if (self.column_id is None) != (self.position is None):
            raise ValueError("column_id and position must be supplied together")
        return self


class CardView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    description: str
    position: int
    created_at: datetime
    updated_at: datetime


class ColumnView(BaseModel):
    id: str
    name: str
    position: int
    cards: list[CardView]


class BoardView(BaseModel):
    columns: list[ColumnView]


class Base(DeclarativeBase):
    pass


class ColumnRecord(Base):
    __tablename__ = "kanban_columns"
    __table_args__ = (
        CheckConstraint("position >= 0", name="column_position_nonnegative"),
        Index("column_position", "position", unique=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CardRecord(Base):
    __tablename__ = "kanban_cards"
    __table_args__ = (
        CheckConstraint("position >= 0", name="card_position_nonnegative"),
        Index("card_column_position", "column_id", "position", unique=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    column_id: Mapped[str] = mapped_column(
        ForeignKey("kanban_columns.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _card(record: CardRecord) -> CardView:
    return CardView.model_validate(record)


class KanbanStore:
    """The transactional authority for the board's structure and content."""

    INITIAL_COLUMNS = ("Backlog", "In Progress", "Done")

    def __init__(self, sessions: sessionmaker[Session],
        now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.sessions = sessions
        self.now = now
        self._seed()

    def _seed(self) -> None:
        with self.sessions.begin() as session:
            if session.scalar(select(ColumnRecord.id).limit(1)) is not None:
                return
            at = self.now()
            session.add_all(ColumnRecord(id=str(uuid4()), name=name, position=position,
                created_at=at, updated_at=at)
                for position, name in enumerate(self.INITIAL_COLUMNS))

    def board(self) -> BoardView:
        with self.sessions() as session:
            columns = session.scalars(select(ColumnRecord).order_by(ColumnRecord.position)).all()
            cards = session.scalars(select(CardRecord).order_by(
                CardRecord.column_id, CardRecord.position)).all()
            grouped: dict[str, list[CardView]] = {column.id: [] for column in columns}
            for record in cards:
                grouped[record.column_id].append(_card(record))
            return BoardView(columns=[ColumnView(id=column.id, name=column.name,
                position=column.position, cards=grouped[column.id]) for column in columns])

    def create_column(self, value: ColumnCreate) -> ColumnView:
        with self.sessions.begin() as session:
            position = len(session.scalars(select(ColumnRecord.id)).all())
            record = ColumnRecord(id=str(uuid4()), name=value.name, position=position,
                created_at=self.now(), updated_at=self.now())
            session.add(record)
            session.flush()
            return ColumnView(id=record.id, name=record.name, position=position, cards=[])

    def update_column(self, column_id: str, value: ColumnUpdate) -> BoardView:
        with self.sessions.begin() as session:
            record = self._column(session, column_id)
            if value.name is not None:
                record.name = value.name
            if value.position is not None:
                ordered = session.scalars(select(ColumnRecord).order_by(ColumnRecord.position)).all()
                if value.position >= len(ordered):
                    raise KanbanError("Column position is outside the board")
                ordered.remove(record)
                ordered.insert(value.position, record)
                self._reindex(session, ordered)
            record.updated_at = self.now()
        return self.board()

    def delete_column(self, column_id: str) -> None:
        with self.sessions.begin() as session:
            record = self._column(session, column_id)
            if session.scalar(select(CardRecord.id).where(CardRecord.column_id == column_id).limit(1)):
                raise KanbanError("Move or delete this column's cards first", "conflict")
            ordered = session.scalars(select(ColumnRecord).order_by(ColumnRecord.position)).all()
            if len(ordered) == 1:
                raise KanbanError("A board must retain at least one column", "conflict")
            session.delete(record)
            ordered.remove(record)
            session.flush()
            self._reindex(session, ordered)

    def create_card(self, value: CardCreate) -> CardView:
        with self.sessions.begin() as session:
            self._column(session, value.column_id)
            position = len(session.scalars(select(CardRecord.id).where(
                CardRecord.column_id == value.column_id)).all())
            at = self.now()
            record = CardRecord(id=str(uuid4()), column_id=value.column_id, title=value.title,
                description=value.description, position=position, created_at=at, updated_at=at)
            session.add(record)
            session.flush()
            return _card(record)

    def update_card(self, card_id: str, value: CardUpdate) -> BoardView:
        with self.sessions.begin() as session:
            record = self._card_record(session, card_id)
            if value.title is not None:
                record.title = value.title
            if value.description is not None:
                record.description = value.description
            if value.column_id is not None and value.position is not None:
                self._move_card(session, record, value.column_id, value.position)
            record.updated_at = self.now()
        return self.board()

    def delete_card(self, card_id: str) -> None:
        with self.sessions.begin() as session:
            record = self._card_record(session, card_id)
            column_id = record.column_id
            session.delete(record)
            session.flush()
            remaining = session.scalars(select(CardRecord).where(
                CardRecord.column_id == column_id).order_by(CardRecord.position)).all()
            self._reindex(session, remaining)

    def _move_card(self, session: Session, record: CardRecord,
        target_column_id: str, target_position: int) -> None:
        self._column(session, target_column_id)
        source_id = record.column_id
        source = session.scalars(select(CardRecord).where(
            CardRecord.column_id == source_id).order_by(CardRecord.position)).all()
        source.remove(record)
        target = source if source_id == target_column_id else session.scalars(select(CardRecord).where(
            CardRecord.column_id == target_column_id).order_by(CardRecord.position)).all()
        if target_position > len(target):
            raise KanbanError("Card position is outside the column")
        if source_id != target_column_id:
            record.position = 200_000
            session.flush()
            self._reindex(session, source)
            record.column_id = target_column_id
        target.insert(target_position, record)
        self._reindex(session, target)

    @staticmethod
    def _reindex(session: Session, records: list[ColumnRecord] | list[CardRecord]) -> None:
        for offset, record in enumerate(records, 1):
            record.position = 100_000 + offset
        session.flush()
        for position, record in enumerate(records):
            record.position = position
        session.flush()

    @staticmethod
    def _column(session: Session, column_id: str) -> ColumnRecord:
        record = session.get(ColumnRecord, column_id)
        if record is None:
            raise KanbanError("Column not found", "missing")
        return record

    @staticmethod
    def _card_record(session: Session, card_id: str) -> CardRecord:
        record = session.get(CardRecord, card_id)
        if record is None:
            raise KanbanError("Card not found", "missing")
        return record
