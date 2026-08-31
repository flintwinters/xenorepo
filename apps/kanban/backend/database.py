"""Durable single-board Kanban domain model and transactional operations."""

from datetime import UTC, datetime
import json
from typing import Callable
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from apps.kanban.backend.schemas import (
    ActivityView, AttachmentView, BoardEdit, BoardView, CardCreate, CardEdit, CardMove, CardView,
    ColumnView, CommentView, KanbanView,
)


class KanbanError(ValueError):
    def __init__(self, message: str, kind: str = "validation") -> None:
        super().__init__(message)
        self.kind = kind


class Base(DeclarativeBase):
    pass


class BoardRecord(Base):
    __tablename__ = "kanban_boards"
    __table_args__ = (CheckConstraint("singleton = 1", name="single_board"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    singleton: Mapped[int] = mapped_column(Integer, unique=True, default=1)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ColumnRecord(Base):
    __tablename__ = "kanban_columns"
    __table_args__ = (Index("active_column_order", "archived_at", "position", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CardRecord(Base):
    __tablename__ = "kanban_cards"
    __table_args__ = (Index("active_card_order", "column_id", "archived_at", "position", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    column_id: Mapped[str] = mapped_column(ForeignKey("kanban_columns.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    assignee: Mapped[str] = mapped_column(String(120), default="")
    labels_json: Mapped[str] = mapped_column(Text, default="[]")
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    position: Mapped[int] = mapped_column(Integer)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommentRecord(Base):
    __tablename__ = "kanban_comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("kanban_cards.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AttachmentRecord(Base):
    __tablename__ = "kanban_attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("kanban_cards.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(120))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ActivityRecord(Base):
    __tablename__ = "kanban_activity"
    __table_args__ = (Index("activity_order", "occurred_at", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    subject_type: Mapped[str] = mapped_column(String(20))
    subject_id: Mapped[str] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(String(300))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _board(value: BoardRecord) -> BoardView:
    return BoardView.model_validate(value, from_attributes=True)


def _column(value: ColumnRecord) -> ColumnView:
    return ColumnView.model_validate(value, from_attributes=True)


def _card(value: CardRecord) -> CardView:
    return CardView(id=value.id, column_id=value.column_id, title=value.title,
        description=value.description, assignee=value.assignee, labels=json.loads(value.labels_json),
        priority=value.priority, position=value.position, archived_at=value.archived_at,
        created_at=value.created_at, updated_at=value.updated_at)


def _comment(value: CommentRecord) -> CommentView:
    return CommentView.model_validate(value, from_attributes=True)


def _attachment(value: AttachmentRecord) -> AttachmentView:
    return AttachmentView.model_validate(value, from_attributes=True)


class KanbanStore:
    """Transactional authority for the one board and all of its children."""

    def __init__(self, sessions: sessionmaker[Session],
        now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.sessions = sessions
        self.now = now
        self._initialize()

    def _initialize(self) -> None:
        with self.sessions.begin() as session:
            if session.scalar(select(BoardRecord)) is not None:
                return
            instant = self.now()
            board = BoardRecord(id=str(uuid4()), singleton=1, name="My board", description="",
                created_at=instant, updated_at=instant)
            session.add(board)
            self._activity(session, "created", "board", board.id, "Created board “My board”")

    def _activity(self, session: Session, kind: str, subject_type: str,
        subject_id: str, summary: str) -> None:
        session.add(ActivityRecord(id=str(uuid4()), kind=kind, subject_type=subject_type,
            subject_id=subject_id, summary=summary[:300], occurred_at=self.now()))

    @staticmethod
    def _required(session: Session, model: type, identity: str, label: str):
        value = session.get(model, identity)
        if value is None:
            raise KanbanError(f"{label} not found", "missing")
        return value

    def view(self) -> KanbanView:
        with self.sessions() as session:
            board = session.scalar(select(BoardRecord))
            assert board is not None
            columns = session.scalars(select(ColumnRecord).order_by(
                ColumnRecord.archived_at.is_not(None), ColumnRecord.position, ColumnRecord.id)).all()
            cards = session.scalars(select(CardRecord).order_by(
                CardRecord.archived_at.is_not(None), CardRecord.column_id,
                CardRecord.position, CardRecord.id)).all()
            comments = session.scalars(select(CommentRecord).order_by(
                CommentRecord.created_at, CommentRecord.id)).all()
            attachments = session.scalars(select(AttachmentRecord).order_by(
                AttachmentRecord.created_at, AttachmentRecord.id)).all()
            activity = session.scalars(select(ActivityRecord).order_by(
                ActivityRecord.occurred_at.desc(), ActivityRecord.id.desc()).limit(200)).all()
            return KanbanView(board=_board(board), columns=[_column(value) for value in columns],
                cards=[_card(value) for value in cards], comments=[_comment(value) for value in comments],
                attachments=[_attachment(value) for value in attachments],
                activity=[ActivityView.model_validate(value) for value in activity])

    def edit_board(self, value: BoardEdit) -> BoardView:
        with self.sessions.begin() as session:
            board = session.scalar(select(BoardRecord))
            assert board is not None
            board.name, board.description, board.updated_at = value.name, value.description, self.now()
            self._activity(session, "edited", "board", board.id, f"Edited board “{board.name}”")
            session.flush()
            return _board(board)

    def create_column(self, name: str) -> ColumnView:
        with self.sessions.begin() as session:
            position = len(session.scalars(select(ColumnRecord).where(
                ColumnRecord.archived_at.is_(None))).all())
            instant = self.now()
            record = ColumnRecord(id=str(uuid4()), name=name, position=position,
                archived_at=None, created_at=instant, updated_at=instant)
            session.add(record)
            self._activity(session, "created", "column", record.id, f"Created column “{name}”")
            session.flush()
            return _column(record)

    def edit_column(self, identity: str, name: str) -> ColumnView:
        with self.sessions.begin() as session:
            record = self._required(session, ColumnRecord, identity, "Column")
            record.name, record.updated_at = name, self.now()
            self._activity(session, "edited", "column", identity, f"Renamed column to “{name}”")
            session.flush()
            return _column(record)

    def move_column(self, identity: str, requested: int) -> ColumnView:
        with self.sessions.begin() as session:
            record = self._required(session, ColumnRecord, identity, "Column")
            if record.archived_at:
                raise KanbanError("Archived columns cannot be moved", "conflict")
            columns = list(session.scalars(select(ColumnRecord).where(
                ColumnRecord.archived_at.is_(None)).order_by(ColumnRecord.position)).all())
            columns.remove(record)
            columns.insert(min(max(requested, 0), len(columns)), record)
            for position, column in enumerate(columns):
                column.position = position
            record.updated_at = self.now()
            self._activity(session, "moved", "column", identity, f"Moved column “{record.name}”")
            session.flush()
            return _column(record)

    def create_card(self, value: CardCreate) -> CardView:
        with self.sessions.begin() as session:
            column = self._required(session, ColumnRecord, value.column_id, "Column")
            if column.archived_at:
                raise KanbanError("Cannot add a card to an archived column", "conflict")
            position = len(self._active_cards(session, value.column_id))
            instant = self.now()
            record = CardRecord(id=str(uuid4()), column_id=value.column_id, title=value.title,
                description=value.description, assignee=value.assignee,
                labels_json=json.dumps(value.labels), priority=value.priority, position=position,
                archived_at=None, created_at=instant, updated_at=instant)
            session.add(record)
            self._activity(session, "created", "card", record.id, f"Created card “{record.title}”")
            session.flush()
            return _card(record)

    def edit_card(self, identity: str, value: CardEdit) -> CardView:
        with self.sessions.begin() as session:
            record = self._required(session, CardRecord, identity, "Card")
            record.title, record.description = value.title, value.description
            record.assignee, record.labels_json = value.assignee, json.dumps(value.labels)
            record.priority, record.updated_at = value.priority, self.now()
            self._activity(session, "edited", "card", identity, f"Edited card “{record.title}”")
            session.flush()
            return _card(record)

    @staticmethod
    def _active_cards(session: Session, column_id: str) -> list[CardRecord]:
        return list(session.scalars(select(CardRecord).where(CardRecord.column_id == column_id,
            CardRecord.archived_at.is_(None)).order_by(CardRecord.position, CardRecord.id)).all())

    def move_card(self, identity: str, value: CardMove) -> CardView:
        with self.sessions.begin() as session:
            record = self._required(session, CardRecord, identity, "Card")
            destination = self._required(session, ColumnRecord, value.column_id, "Column")
            if record.archived_at or destination.archived_at:
                raise KanbanError("Archived cards and columns cannot receive moves", "conflict")
            source = self._active_cards(session, record.column_id)
            source.remove(record)
            for position, card in enumerate(source):
                card.position = position
            target = source if record.column_id == value.column_id else self._active_cards(session, value.column_id)
            position = min(max(value.position, 0), len(target))
            target.insert(position, record)
            record.column_id = value.column_id
            for index, card in enumerate(target):
                card.position = index
            record.updated_at = self.now()
            self._activity(session, "moved", "card", identity, f"Moved card “{record.title}”")
            session.flush()
            return _card(record)

    def archive(self, kind: str, identity: str, restore: bool = False) -> None:
        models = {"column": ColumnRecord, "card": CardRecord,
            "comment": CommentRecord, "attachment": AttachmentRecord}
        model = models.get(kind)
        if model is None:
            raise KanbanError("Unknown archive subject")
        with self.sessions.begin() as session:
            record = self._required(session, model, identity, kind.title())
            self._validate_archive(session, kind, record, restore)
            record.archived_at = None if restore else self.now()
            self._compact_after_archive(session, kind, record)
            action = "restored" if restore else "archived"
            title = getattr(record, "title", getattr(record, "name", kind))
            self._activity(session, action, kind, identity, f"{action.title()} {kind} “{title}”")

    def _validate_archive(self, session: Session, kind: str, record, restore: bool) -> None:
        if restore:
            self._validate_restore(session, kind, record)
        elif kind == "column":
            self._validate_column_archive(session, record)

    def _validate_restore(self, session: Session, kind: str, record) -> None:
        if kind == "card":
            self._require_active_parent(session, ColumnRecord, record.column_id,
                "Column", "Restore the card's column first")
        elif kind in {"comment", "attachment"}:
            self._require_active_parent(session, CardRecord, record.card_id,
                "Card", "Restore the parent card first")

    def _require_active_parent(self, session: Session, model: type, identity: str,
        label: str, message: str) -> None:
        parent = self._required(session, model, identity, label)
        if parent.archived_at:
            raise KanbanError(message, "conflict")

    def _validate_column_archive(self, session: Session, record: ColumnRecord) -> None:
        if self._active_cards(session, record.id):
            raise KanbanError("Archive every card in the column first", "conflict")

    def _compact_after_archive(self, session: Session, kind: str, record) -> None:
        if kind == "card":
            for position, card in enumerate(self._active_cards(session, record.column_id)):
                card.position = position
        if kind == "column":
            columns = session.scalars(select(ColumnRecord).where(
                ColumnRecord.archived_at.is_(None)).order_by(ColumnRecord.position)).all()
            for position, column in enumerate(columns):
                column.position = position

    def add_comment(self, card_id: str, body: str) -> CommentView:
        with self.sessions.begin() as session:
            card = self._required(session, CardRecord, card_id, "Card")
            if card.archived_at:
                raise KanbanError("Cannot comment on an archived card", "conflict")
            instant = self.now()
            record = CommentRecord(id=str(uuid4()), card_id=card_id, body=body,
                archived_at=None, created_at=instant, updated_at=instant)
            session.add(record)
            self._activity(session, "created", "comment", record.id, f"Commented on “{card.title}”")
            session.flush()
            return _comment(record)

    def edit_comment(self, identity: str, body: str) -> CommentView:
        with self.sessions.begin() as session:
            record = self._required(session, CommentRecord, identity, "Comment")
            record.body, record.updated_at = body, self.now()
            self._activity(session, "edited", "comment", identity, "Edited a comment")
            session.flush()
            return _comment(record)

    def add_attachment(self, card_id: str, *, kind: str, title: str, url: str | None = None,
        storage_name: str | None = None, original_name: str | None = None,
        media_type: str | None = None) -> AttachmentView:
        with self.sessions.begin() as session:
            card = self._required(session, CardRecord, card_id, "Card")
            if card.archived_at:
                raise KanbanError("Cannot attach to an archived card", "conflict")
            record = AttachmentRecord(id=str(uuid4()), card_id=card_id, kind=kind, title=title,
                url=url, storage_name=storage_name, original_name=original_name,
                media_type=media_type, archived_at=None, created_at=self.now())
            session.add(record)
            self._activity(session, "created", "attachment", record.id,
                f"Attached “{title}” to “{card.title}”")
            session.flush()
            return _attachment(record)

    def edit_attachment(self, identity: str, title: str, url: str | None) -> AttachmentView:
        with self.sessions.begin() as session:
            record = self._required(session, AttachmentRecord, identity, "Attachment")
            if record.kind == "link" and url is None:
                raise KanbanError("Link attachments require a URL")
            if record.kind == "upload" and url is not None:
                raise KanbanError("Upload attachments cannot have a URL")
            record.title, record.url = title, url
            self._activity(session, "edited", "attachment", identity, f"Edited attachment “{title}”")
            session.flush()
            return _attachment(record)

    def attachment(self, identity: str) -> AttachmentRecord:
        with self.sessions() as session:
            record = self._required(session, AttachmentRecord, identity, "Attachment")
            session.expunge(record)
            return record
