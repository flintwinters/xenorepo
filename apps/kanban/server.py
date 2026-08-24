"""Single FastAPI runtime for the durable Kanban board."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from apps.kanban.database import (
    Base,
    Board,
    BoardStore,
    Card,
    CardCreate,
    CardUpdate,
    InvalidPositionError,
    UnknownColumnError,
)
from monotools.appkit import create_app_context
from monotools.runtime import create_application


DEFAULT_DATABASE = Path(__file__).parent / "data" / "kanban.db"


async def unknown_column(_: Request, error: UnknownColumnError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": f"Unknown column: {error}"})


async def invalid_position(_: Request, error: InvalidPositionError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": f"Invalid destination index: {error}"},
    )


def create_app(database_url: str | None = None, store: BoardStore | None = None) -> FastAPI:
    context = create_app_context(
        "kanban",
        metadata=Base.metadata,
        default_database=DEFAULT_DATABASE,
        environment_key="KANBAN_DATABASE_URL",
        database_url=database_url,
    )
    board = store or BoardStore.with_demo_cards(context.require_sessions())
    application = create_application("kanban")
    application.state.board = board
    application.add_exception_handler(UnknownColumnError, unknown_column)
    application.add_exception_handler(InvalidPositionError, invalid_position)

    @application.get("/api/board", response_model=Board)
    async def get_board() -> Board:
        return board.snapshot()

    @application.post("/api/cards", response_model=Card, status_code=status.HTTP_201_CREATED)
    async def create_card(card: CardCreate) -> Card:
        return board.create(card)

    @application.patch("/api/cards/{card_id}", response_model=Card)
    async def update_card(card_id: str, update: CardUpdate) -> Card:
        card = board.update(card_id, update)
        if card is None:
            raise HTTPException(status_code=404, detail="Card not found")
        return card

    @application.delete("/api/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_card(card_id: str) -> None:
        if not board.delete(card_id):
            raise HTTPException(status_code=404, detail="Card not found")

    @application.post("/api/undo", response_model=Board)
    async def undo() -> Board:
        snapshot = board.undo()
        if snapshot is None:
            raise HTTPException(status_code=409, detail="Nothing to undo")
        return snapshot

    @application.post("/api/redo", response_model=Board)
    async def redo() -> Board:
        snapshot = board.redo()
        if snapshot is None:
            raise HTTPException(status_code=409, detail="Nothing to redo")
        return snapshot

    return application


app = create_app()
