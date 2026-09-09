"""Shared invariants for the Kanban tag namespace."""

from datetime import datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session


def ensure_board_tag(session: Session, tag_model: type, board, instant: datetime,
    conflict_error: type[Exception]) -> None:
    record = session.scalar(select(tag_model).where(tag_model.board_id == board.id))
    key = board.name.casefold()
    conflict = session.scalar(select(tag_model).where(tag_model.key == key))
    if record is None and conflict is None:
        session.add(tag_model(id=str(uuid5(NAMESPACE_URL, f"kanban:board-tag:{board.id}")),
            key=key, name=board.name, kind="board", board_id=board.id, created_at=instant))
    elif record is not None:
        if conflict is not None and conflict.id != record.id:
            raise conflict_error(f"Tag “{board.name}” already exists", "conflict")
        record.key, record.name = key, board.name


def ensure_regular_tag(session: Session, tag_model: type, name: str, instant: datetime,
    conflict_error: type[Exception], allow_board: bool = False) -> None:
    key = name.casefold()
    existing = session.scalar(select(tag_model).where(tag_model.key == key))
    if existing is not None:
        if existing.kind == "board" and not allow_board:
            raise conflict_error(f"“{name}” is a board tag", "conflict")
        return
    session.add(tag_model(id=str(uuid4()), key=key, name=name, kind="tag",
        board_id=None, created_at=instant))


def create_regular_tag(session: Session, tag_model: type, name: str, instant: datetime,
    conflict_error: type[Exception]):
    key = name.casefold()
    if session.scalar(select(tag_model).where(tag_model.key == key)) is not None:
        raise conflict_error(f"Tag “{name}” already exists", "conflict")
    record = tag_model(id=str(uuid4()), key=key, name=name, kind="tag",
        board_id=None, created_at=instant)
    session.add(record)
    return record
