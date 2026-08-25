"""Single FastAPI runtime for the durable Kanban board."""

from pathlib import Path

from fastapi import FastAPI, Request, status

from apps.kanban.backend.database import (
    Base,
    Board,
    BoardError,
    BoardStore,
    Card,
    CardCreate,
    CardUpdate,
    remove_browser_fixture_contamination,
)
from monotools.appkit import create_app_context
from monotools.http import domain_error_handler, enforce_same_origin
from monotools.runtime import create_application


DEFAULT_DATABASE = Path(__file__).parent.parent / "data" / "kanban.db"


def create_app(database_url: str | None = None, store: BoardStore | None = None) -> FastAPI:
    context = create_app_context(
        "kanban",
        metadata=Base.metadata,
        default_database=DEFAULT_DATABASE,
        environment_key="KANBAN_DATABASE_URL",
        database_url=database_url,
        prepare=remove_browser_fixture_contamination,
    )
    board = store or BoardStore.with_demo_cards(context.require_sessions())
    application = create_application("kanban")
    application.state.board = board
    application.add_exception_handler(BoardError, domain_error_handler(statuses={
        "conflict": 409, "forbidden": 403, "missing": 404, "validation": 422,
    }))

    def enforce_origin(request: Request) -> None:
        enforce_same_origin(request, lambda message: BoardError(message, "forbidden"))

    @application.get("/api/board", response_model=Board)
    async def get_board() -> Board:
        return board.snapshot()

    @application.post("/api/cards", response_model=Card, status_code=status.HTTP_201_CREATED)
    async def create_card(card: CardCreate, request: Request) -> Card:
        enforce_origin(request)
        return board.create(card)

    @application.patch("/api/cards/{card_id}", response_model=Card)
    async def update_card(card_id: str, update: CardUpdate, request: Request) -> Card:
        enforce_origin(request)
        card = board.update(card_id, update)
        if card is None:
            raise BoardError("Card not found", "missing")
        return card

    @application.delete("/api/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_card(card_id: str, request: Request) -> None:
        enforce_origin(request)
        if not board.delete(card_id):
            raise BoardError("Card not found", "missing")

    @application.post("/api/undo", response_model=Board)
    async def undo(request: Request) -> Board:
        enforce_origin(request)
        snapshot = board.undo()
        if snapshot is None:
            raise BoardError("Nothing to undo", "conflict")
        return snapshot

    @application.post("/api/redo", response_model=Board)
    async def redo(request: Request) -> Board:
        enforce_origin(request)
        snapshot = board.redo()
        if snapshot is None:
            raise BoardError("Nothing to redo", "conflict")
        return snapshot

    return application


app = create_app()
