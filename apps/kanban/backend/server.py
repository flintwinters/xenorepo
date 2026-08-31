"""FastAPI runtime for Kanban Board."""

from pathlib import Path

from fastapi import FastAPI, Request, status

from apps.kanban.backend.database import (
    Base, BoardView, CardCreate, CardUpdate, CardView, ColumnCreate, ColumnUpdate,
    ColumnView, KanbanError, KanbanStore,
)
from monotools.runtime.appkit import create_app_context
from monotools.runtime.application import create_application
from monotools.runtime.http import domain_error_handler, enforce_same_origin


DEFAULT_DATABASE = Path(__file__).parent.parent / "data" / "kanban.db"


def create_app(database_url: str | None = None, store: KanbanStore | None = None) -> FastAPI:
    context = create_app_context("kanban", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="KANBAN_DATABASE_URL",
        database_url=database_url)
    board = store or KanbanStore(context.require_sessions(), now=context.clock.now)
    application = create_application("kanban")
    application.state.kanban = board
    application.add_exception_handler(KanbanError, domain_error_handler(statuses={
        "conflict": 409, "forbidden": 403, "missing": 404, "validation": 422,
    }))

    def require_origin(request: Request) -> None:
        enforce_same_origin(request, lambda message: KanbanError(message, "forbidden"))

    @application.get("/api/board", response_model=BoardView)
    async def get_board() -> BoardView:
        return board.board()

    @application.post("/api/columns", response_model=ColumnView,
        status_code=status.HTTP_201_CREATED)
    async def create_column(value: ColumnCreate, request: Request) -> ColumnView:
        require_origin(request)
        return board.create_column(value)

    @application.patch("/api/columns/{column_id}", response_model=BoardView)
    async def update_column(column_id: str, value: ColumnUpdate, request: Request) -> BoardView:
        require_origin(request)
        return board.update_column(column_id, value)

    @application.delete("/api/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_column(column_id: str, request: Request) -> None:
        require_origin(request)
        board.delete_column(column_id)

    @application.post("/api/cards", response_model=CardView,
        status_code=status.HTTP_201_CREATED)
    async def create_card(value: CardCreate, request: Request) -> CardView:
        require_origin(request)
        return board.create_card(value)

    @application.patch("/api/cards/{card_id}", response_model=BoardView)
    async def update_card(card_id: str, value: CardUpdate, request: Request) -> BoardView:
        require_origin(request)
        return board.update_card(card_id, value)

    @application.delete("/api/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_card(card_id: str, request: Request) -> None:
        require_origin(request)
        board.delete_card(card_id)

    return application


app = create_app()
