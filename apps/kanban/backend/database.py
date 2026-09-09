"""Durable single-board Kanban domain model and transactional operations."""

from datetime import UTC, datetime, timedelta
import json
from typing import Callable
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, delete, inspect, select, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from apps.kanban.backend.schemas import (
    ActivityView, AttachmentView, BoardEdit, BoardView, CardCreate, CardEdit, CardMove, CardView,
    BoardDetailsEdit, BoardImport, ColumnView, ImportResult, KanbanView, LogView, TagCreate, TagView,
)
from apps.kanban.backend.tag_catalog import create_regular_tag, ensure_board_tag, ensure_regular_tag


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


class BoardSettingsRecord(Base):
    __tablename__ = "kanban_board_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_board_settings"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Retained only so installations created by older releases remain writable.
    legacy_priority: Mapped[str] = mapped_column("default_priority", String(10), default="normal")
    background_color: Mapped[str] = mapped_column(String(7), default="#1d2021")
    accent_color: Mapped[str] = mapped_column(String(7), default="#fabd2f")
    column_colors_json: Mapped[str] = mapped_column(Text, default="{}")
    # Retained only so installations created by older releases remain writable.
    legacy_card_colors_json: Mapped[str] = mapped_column("card_colors_json", Text, default="{}")
    # Retain the physical column name so existing installations preserve tag colors.
    tag_colors_json: Mapped[str] = mapped_column("label_colors_json", Text, default="{}")


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
    # Retained only to migrate descriptions created by older releases.
    legacy_description: Mapped[str] = mapped_column("description", Text, default="")
    # Retained only so installations created by older releases remain writable.
    legacy_assignee: Mapped[str] = mapped_column("assignee", String(120), default="")
    # Retain the physical column name so existing installations preserve card tags.
    tags_json: Mapped[str] = mapped_column("labels_json", Text, default="[]")
    # Retained only so installations created by older releases remain writable.
    legacy_priority: Mapped[str] = mapped_column("priority", String(10), default="normal")
    position: Mapped[int] = mapped_column(Integer)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TagRecord(Base):
    __tablename__ = "kanban_tags"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10))
    board_id: Mapped[str | None] = mapped_column(ForeignKey("kanban_boards.id"), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LegacyCommentRecord(Base):
    __tablename__ = "kanban_comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("kanban_cards.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LogRecord(Base):
    __tablename__ = "kanban_logs"
    __table_args__ = (Index("card_log_order", "card_id", "created_at", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("kanban_cards.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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


def _board(value: BoardRecord, settings: BoardSettingsRecord) -> BoardView:
    return BoardView(id=value.id, name=value.name, description=value.description,
        created_at=value.created_at, updated_at=value.updated_at,
        background_color=settings.background_color,
        accent_color=settings.accent_color, tag_colors=json.loads(settings.tag_colors_json))


def _column(value: ColumnRecord, colors: dict[str, str]) -> ColumnView:
    return ColumnView(id=value.id, name=value.name, position=value.position,
        archived_at=value.archived_at, color=colors.get(value.id, "#665c54"))


def _card(value: CardRecord) -> CardView:
    return CardView(id=value.id, column_id=value.column_id, title=value.title,
        tags=json.loads(value.tags_json),
        position=value.position, archived_at=value.archived_at,
        created_at=value.created_at, updated_at=value.updated_at)


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
            self._upgrade_tag_catalog(session)
            board = session.scalar(select(BoardRecord))
            if board is None:
                instant = self.now()
                board = BoardRecord(id=str(uuid4()), singleton=1, name="My board", description="",
                    created_at=instant, updated_at=instant)
                session.add(board)
                self._activity(session, "created", "board", board.id, "Created board “My board”")
            if session.get(BoardSettingsRecord, 1) is None:
                session.add(BoardSettingsRecord(id=1))
            self._migrate_card_text(session)
            self._migrate_tags(session, board)

    @staticmethod
    def _upgrade_tag_catalog(session: Session) -> None:
        columns = {value["name"] for value in inspect(session.get_bind()).get_columns("kanban_tags")}
        if "board_id" not in columns:
            session.execute(text("ALTER TABLE kanban_tags ADD COLUMN board_id VARCHAR(36)"))
            session.execute(text("DELETE FROM kanban_tags WHERE kind = 'board'"))

    def _migrate_tags(self, session: Session, board: BoardRecord) -> None:
        instant = self.now()
        ensure_board_tag(session, TagRecord, board, instant, KanbanError)
        for card in session.scalars(select(CardRecord)).all():
            for name in json.loads(card.tags_json):
                ensure_regular_tag(session, TagRecord, name, instant, KanbanError, allow_board=True)
        settings = session.get(BoardSettingsRecord, 1)
        if settings is not None:
            for name in json.loads(settings.tag_colors_json):
                ensure_regular_tag(session, TagRecord, name, instant, KanbanError, allow_board=True)

    @staticmethod
    def _migrate_card_text(session: Session) -> None:
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        for card in session.scalars(select(CardRecord)).all():
            body = card.legacy_description.strip()
            identity = str(uuid5(NAMESPACE_URL, f"kanban:description:{card.id}"))
            migrated = session.get(LogRecord, identity)
            if body and migrated is None:
                session.add(LogRecord(id=identity, card_id=card.id, body=body, created_at=epoch))
            elif not body and migrated is not None:
                card.legacy_description = migrated.body
        for comment in session.scalars(select(LegacyCommentRecord)).all():
            identity = str(uuid5(NAMESPACE_URL, f"kanban:comment:{comment.id}"))
            if session.get(LogRecord, identity) is None:
                session.add(LogRecord(id=identity, card_id=comment.card_id,
                    body=comment.body, created_at=comment.created_at))
            session.delete(comment)

    def _activity(self, session: Session, kind: str, subject_type: str,
        subject_id: str, summary: str) -> None:
        session.add(ActivityRecord(id=str(uuid4()), kind=kind, subject_type=subject_type,
            subject_id=subject_id, summary=summary[:300], occurred_at=self.now()))

    @staticmethod
    def _required(session: Session, model: type, identity: str | int, label: str):
        value = session.get(model, identity)
        if value is None: raise KanbanError(f"{label} not found", "missing")
        return value

    def view(self) -> KanbanView:
        with self.sessions() as session:
            board = session.scalar(select(BoardRecord))
            assert board is not None
            settings = session.get(BoardSettingsRecord, 1)
            assert settings is not None
            column_colors = json.loads(settings.column_colors_json)
            columns = session.scalars(select(ColumnRecord).order_by(
                ColumnRecord.archived_at.is_not(None), ColumnRecord.position, ColumnRecord.id)).all()
            cards = session.scalars(select(CardRecord).order_by(
                CardRecord.archived_at.is_not(None), CardRecord.column_id,
                CardRecord.position, CardRecord.id)).all()
            logs = session.scalars(select(LogRecord).order_by(
                LogRecord.created_at, LogRecord.id)).all()
            attachments = session.scalars(select(AttachmentRecord).order_by(
                AttachmentRecord.created_at, AttachmentRecord.id)).all()
            tag_records = session.scalars(select(TagRecord).order_by(TagRecord.kind, TagRecord.name)).all()
            activity = session.scalars(select(ActivityRecord).order_by(
                ActivityRecord.occurred_at.desc(), ActivityRecord.id.desc()).limit(200)).all()
            tag_colors = json.loads(settings.tag_colors_json)
            return KanbanView(board=_board(board, settings),
                columns=[_column(value, column_colors) for value in columns],
                cards=[_card(value) for value in cards],
                tags=[TagView(id=value.id, name=value.name, kind=value.kind,
                    color=settings.accent_color if value.kind == "board"
                    else tag_colors.get(value.key, settings.accent_color)) for value in tag_records],
                logs=[LogView.model_validate(value) for value in logs],
                attachments=[_attachment(value) for value in attachments],
                activity=[ActivityView.model_validate(value) for value in activity])

    def edit_board(self, value: BoardEdit) -> BoardView:
        with self.sessions.begin() as session:
            board = session.scalar(select(BoardRecord))
            assert board is not None
            settings = session.get(BoardSettingsRecord, 1)
            assert settings is not None
            board.name, board.description, board.updated_at = value.name, value.description, self.now()
            settings.background_color, settings.accent_color = value.background_color, value.accent_color
            settings.tag_colors_json = json.dumps({key.casefold(): color
                for key, color in value.tag_colors.items()})
            for tag in value.tag_colors:
                ensure_regular_tag(session, TagRecord, tag, board.updated_at, KanbanError)
            ensure_board_tag(session, TagRecord, board, board.updated_at, KanbanError)
            self._activity(session, "edited", "board", board.id, f"Edited board “{board.name}”")
            session.flush()
            return _board(board, settings)

    def import_board(self, value: BoardImport, replace: bool) -> ImportResult:
        """Import one validated relational document in a single transaction."""
        with self.sessions.begin() as session:
            board = session.scalar(select(BoardRecord))
            settings = session.get(BoardSettingsRecord, 1)
            assert board is not None and settings is not None
            if replace:
                self._replace_import_state(session, board, settings, value)
            column_offset = 0 if replace else self._active_column_count(session)
            instant = self.now()
            ensure_board_tag(session, TagRecord, board, instant, KanbanError)
            for tag in {*value.tags, *value.tag_colors}:
                ensure_regular_tag(session, TagRecord, tag, instant, KanbanError)
            column_colors = {} if replace else json.loads(settings.column_colors_json)
            column_ids = self._import_columns(session, value, instant, column_offset, column_colors)
            session.flush()
            card_ids = self._import_cards(session, value, instant, column_ids)
            session.flush()
            self._import_children(session, value, instant, card_ids)
            settings.column_colors_json = json.dumps(column_colors)
            return self._record_import(session, board.id, value, replace)

    def _replace_import_state(self, session: Session, board: BoardRecord,
        settings: BoardSettingsRecord, value: BoardImport) -> None:
        for model in (AttachmentRecord, LegacyCommentRecord, LogRecord,
            CardRecord, TagRecord, ColumnRecord, ActivityRecord):
            session.execute(delete(model))
        session.flush()
        board.name, board.description, board.updated_at = value.name, value.description, self.now()
        settings.background_color, settings.accent_color = value.background_color, value.accent_color
        settings.tag_colors_json = json.dumps({key.casefold(): color
            for key, color in value.tag_colors.items()})

    @staticmethod
    def _active_column_count(session: Session) -> int:
        return len(session.scalars(select(ColumnRecord).where(
            ColumnRecord.archived_at.is_(None))).all())

    def _import_columns(self, session: Session, value: BoardImport, instant: datetime,
        offset: int, colors: dict[str, str]) -> dict[str, str]:
        identities = {source.id: str(uuid4()) for source in value.columns}
        for position, source in enumerate(value.columns, start=offset):
            identity = identities[source.id]
            record = ColumnRecord(id=identity, name=source.name, position=position,
                archived_at=None, created_at=instant, updated_at=instant)
            session.add(record)
            colors[identity] = source.color
        return identities

    def _import_cards(self, session: Session, value: BoardImport, instant: datetime,
        column_ids: dict[str, str]) -> dict[str, str]:
        identities = {source.id: str(uuid4()) for source in value.cards}
        positions: dict[str, int] = {}
        for source in value.cards:
            for tag in source.tags:
                ensure_regular_tag(session, TagRecord, tag, instant, KanbanError)
            column_id = column_ids[source.column_id]
            position = positions.get(column_id, 0)
            positions[column_id] = position + 1
            identity = identities[source.id]
            session.add(CardRecord(id=identity, column_id=column_id, title=source.title,
                legacy_description="", legacy_assignee="",
                tags_json=json.dumps(source.tags), legacy_priority="normal", position=position,
                archived_at=None, created_at=instant, updated_at=instant))
        return identities

    @staticmethod
    def _import_children(session: Session, value: BoardImport, instant: datetime,
        card_ids: dict[str, str]) -> None:
        for source in value.logs:
            session.add(LogRecord(id=str(uuid4()), card_id=card_ids[source.card_id],
                body=source.body, created_at=source.created_at))
        for order, source in enumerate(value.attachments):
            session.add(AttachmentRecord(id=str(uuid4()), card_id=card_ids[source.card_id],
                kind="link", title=source.title, url=str(source.url), storage_name=None,
                original_name=None, media_type=None, archived_at=None,
                created_at=instant + timedelta(microseconds=order)))

    def _record_import(self, session: Session, board_id: str,
        value: BoardImport, replace: bool) -> ImportResult:
        mode = "replace" if replace else "append"
        self._activity(session, "imported", "board", board_id,
            f"{mode.title()} imported {len(value.cards)} cards")
        return ImportResult(mode=mode, columns=len(value.columns), cards=len(value.cards),
            logs=len(value.logs), attachments=len(value.attachments))

    def edit_board_details(self, value: BoardDetailsEdit) -> BoardView:
        with self.sessions.begin() as session:
            board = session.scalar(select(BoardRecord))
            assert board is not None
            settings = session.get(BoardSettingsRecord, 1)
            assert settings is not None
            board.name, board.description, board.updated_at = value.name, value.description, self.now()
            ensure_board_tag(session, TagRecord, board, board.updated_at, KanbanError)
            self._activity(session, "edited", "board", board.id, f"Edited board “{board.name}”")
            session.flush()
            return _board(board, settings)

    def set_tag_color(self, tag: str, color: str) -> BoardView:
        with self.sessions.begin() as session:
            board = session.scalar(select(BoardRecord))
            assert board is not None
            settings = session.get(BoardSettingsRecord, 1)
            assert settings is not None
            ensure_regular_tag(session, TagRecord, tag, self.now(), KanbanError)
            colors = json.loads(settings.tag_colors_json)
            colors[tag.casefold()] = color
            settings.tag_colors_json = json.dumps(colors)
            self._activity(session, "edited", "board", board.id, f"Changed tag “{tag}” color")
            session.flush()
            return _board(board, settings)

    def create_tag(self, value: TagCreate) -> TagView:
        with self.sessions.begin() as session:
            record = create_regular_tag(session, TagRecord, value.name, self.now(), KanbanError)
            settings = self._required(session, BoardSettingsRecord, 1, "Board settings")
            colors = {**json.loads(settings.tag_colors_json), record.key: value.color}
            settings.tag_colors_json = json.dumps(colors)
            self._activity(session, "created", "tag", record.id, f"Created tag “{record.name}”")
            return TagView(id=record.id, name=record.name, kind="tag", color=value.color)

    def create_column(self, name: str, color: str) -> ColumnView:
        with self.sessions.begin() as session:
            position = len(session.scalars(select(ColumnRecord).where(
                ColumnRecord.archived_at.is_(None))).all())
            instant = self.now()
            record = ColumnRecord(id=str(uuid4()), name=name, position=position,
                archived_at=None, created_at=instant, updated_at=instant)
            session.add(record)
            colors = self._set_column_color(session, record.id, color)
            self._activity(session, "created", "column", record.id, f"Created column “{name}”")
            session.flush()
            return _column(record, colors)

    def edit_column(self, identity: str, name: str, color: str) -> ColumnView:
        with self.sessions.begin() as session:
            record = self._required(session, ColumnRecord, identity, "Column")
            record.name, record.updated_at = name, self.now()
            colors = self._set_column_color(session, identity, color)
            self._activity(session, "edited", "column", identity, f"Renamed column to “{name}”")
            session.flush()
            return _column(record, colors)

    def _set_column_color(self, session: Session, identity: str, color: str) -> dict[str, str]:
        settings = session.get(BoardSettingsRecord, 1)
        assert settings is not None
        colors = json.loads(settings.column_colors_json)
        colors[identity] = color
        settings.column_colors_json = json.dumps(colors)
        return colors

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
            settings = session.get(BoardSettingsRecord, 1)
            assert settings is not None
            return _column(record, json.loads(settings.column_colors_json))

    def create_card(self, value: CardCreate) -> CardView:
        with self.sessions.begin() as session:
            column = self._required(session, ColumnRecord, value.column_id, "Column")
            if column.archived_at:
                raise KanbanError("Cannot add a card to an archived column", "conflict")
            position = len(self._active_cards(session, value.column_id))
            instant = self.now()
            record = CardRecord(id=str(uuid4()), column_id=value.column_id, title=value.title,
                legacy_description="", legacy_assignee="",
                tags_json=json.dumps(value.tags), legacy_priority="normal", position=position,
                archived_at=None, created_at=instant, updated_at=instant)
            session.add(record)
            for tag in value.tags:
                ensure_regular_tag(session, TagRecord, tag, instant, KanbanError)
            self._activity(session, "created", "card", record.id, f"Created card “{record.title}”")
            session.flush()
            return _card(record)

    def edit_card(self, identity: str, value: CardEdit) -> CardView:
        with self.sessions.begin() as session:
            record = self._required(session, CardRecord, identity, "Card")
            record.title = value.title
            instant = self.now()
            for tag in value.tags:
                ensure_regular_tag(session, TagRecord, tag, instant, KanbanError)
            record.tags_json = json.dumps(value.tags)
            record.updated_at = instant
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
        models = {"column": ColumnRecord, "card": CardRecord, "attachment": AttachmentRecord}
        model = models.get(kind)
        if model is None:
            raise KanbanError("Unknown archive subject")
        with self.sessions.begin() as session:
            record = self._required(session, model, identity, kind.title())
            self._validate_archive(session, kind, record, restore)
            if kind == "column" and not restore:
                self._archive_column_cards(session, record)
            record.archived_at = None if restore else self.now()
            self._compact_after_archive(session, kind, record)
            action = "restored" if restore else "archived"
            title = getattr(record, "title", getattr(record, "name", kind))
            self._activity(session, action, kind, identity, f"{action.title()} {kind} “{title}”")

    def _validate_archive(self, session: Session, kind: str, record, restore: bool) -> None:
        if restore:
            self._validate_restore(session, kind, record)

    def _validate_restore(self, session: Session, kind: str, record) -> None:
        if kind == "card":
            self._require_active_parent(session, ColumnRecord, record.column_id,
                "Column", "Restore the card's column first")
        elif kind == "attachment":
            self._require_active_parent(session, CardRecord, record.card_id,
                "Card", "Restore the parent card first")

    def _require_active_parent(self, session: Session, model: type, identity: str,
        label: str, message: str) -> None:
        parent = self._required(session, model, identity, label)
        if parent.archived_at:
            raise KanbanError(message, "conflict")

    def _archive_column_cards(self, session: Session, column: ColumnRecord) -> None:
        for card in self._active_cards(session, column.id):
            card.archived_at = self.now()
            self._activity(session, "archived", "card", card.id,
                f"Archived card “{card.title}” with column “{column.name}”")

    def _compact_after_archive(self, session: Session, kind: str, record) -> None:
        if kind == "card":
            for position, card in enumerate(self._active_cards(session, record.column_id)):
                card.position = position
        if kind == "column":
            columns = session.scalars(select(ColumnRecord).where(
                ColumnRecord.archived_at.is_(None)).order_by(ColumnRecord.position)).all()
            for position, column in enumerate(columns):
                column.position = position

    def add_log(self, card_id: str, body: str) -> LogView:
        with self.sessions.begin() as session:
            card = self._required(session, CardRecord, card_id, "Card")
            if card.archived_at:
                raise KanbanError("Cannot log work on an archived card", "conflict")
            record = LogRecord(id=str(uuid4()), card_id=card_id, body=body, created_at=self.now())
            session.add(record)
            self._activity(session, "created", "log", record.id, f"Logged work on “{card.title}”")
            session.flush()
            return LogView.model_validate(record)

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
