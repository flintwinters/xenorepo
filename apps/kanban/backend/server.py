"""FastAPI runtime for the local single-board Kanban application."""

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.responses import Response

from apps.kanban.backend.database import Base, KanbanError, KanbanStore
from apps.kanban.backend.schemas import (
    AttachmentEdit, AttachmentView, BoardEdit, BoardView, CardCreate, CardEdit, CardMove, CardView,
    ColumnCreate, ColumnEdit, ColumnView, CommentInput, CommentView, KanbanView, LinkInput,
    PositionInput,
)
from monotools.runtime.appkit import create_app_context
from monotools.runtime.application import create_application
from monotools.runtime.http import domain_error_handler, enforce_same_origin


DIRECTORY = Path(__file__).parent.parent
DEFAULT_DATABASE = DIRECTORY / "data" / "kanban.db"
DEFAULT_UPLOADS = DIRECTORY / "data" / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def create_app(database_url: str | None = None, store: KanbanStore | None = None,
    uploads: Path = DEFAULT_UPLOADS) -> FastAPI:
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

    @application.get("/api/board", response_model=KanbanView)
    async def get_board() -> KanbanView:
        return board.view()

    @application.patch("/api/board", response_model=BoardView)
    async def edit_board(value: BoardEdit, request: Request) -> BoardView:
        require_origin(request)
        return board.edit_board(value)

    @application.post("/api/columns", response_model=ColumnView,
        status_code=status.HTTP_201_CREATED)
    async def create_column(value: ColumnCreate, request: Request) -> ColumnView:
        require_origin(request)
        return board.create_column(value.name)

    @application.patch("/api/columns/{column_id}", response_model=ColumnView)
    async def edit_column(column_id: str, value: ColumnEdit, request: Request) -> ColumnView:
        require_origin(request)
        return board.edit_column(column_id, value.name)

    @application.put("/api/columns/{column_id}/position", response_model=ColumnView)
    async def move_column(column_id: str, value: PositionInput, request: Request) -> ColumnView:
        require_origin(request)
        return board.move_column(column_id, value.position)

    @application.post("/api/cards", response_model=CardView,
        status_code=status.HTTP_201_CREATED)
    async def create_card(value: CardCreate, request: Request) -> CardView:
        require_origin(request)
        return board.create_card(value)

    @application.patch("/api/cards/{card_id}", response_model=CardView)
    async def edit_card(card_id: str, value: CardEdit, request: Request) -> CardView:
        require_origin(request)
        return board.edit_card(card_id, value)

    @application.put("/api/cards/{card_id}/position", response_model=CardView)
    async def move_card(card_id: str, value: CardMove, request: Request) -> CardView:
        require_origin(request)
        return board.move_card(card_id, value)

    @application.post("/api/cards/{card_id}/comments", response_model=CommentView,
        status_code=status.HTTP_201_CREATED)
    async def add_comment(card_id: str, value: CommentInput, request: Request) -> CommentView:
        require_origin(request)
        return board.add_comment(card_id, value.body)

    @application.patch("/api/comments/{comment_id}", response_model=CommentView)
    async def edit_comment(comment_id: str, value: CommentInput, request: Request) -> CommentView:
        require_origin(request)
        return board.edit_comment(comment_id, value.body)

    @application.post("/api/cards/{card_id}/links", response_model=AttachmentView,
        status_code=status.HTTP_201_CREATED)
    async def add_link(card_id: str, value: LinkInput, request: Request) -> AttachmentView:
        require_origin(request)
        return board.add_attachment(card_id, kind="link", title=value.title, url=str(value.url))

    @application.post("/api/cards/{card_id}/uploads", response_model=AttachmentView,
        status_code=status.HTTP_201_CREATED)
    async def add_upload(request: Request, card_id: str) -> AttachmentView:
        require_origin(request)
        clean_title = request.headers.get("x-attachment-title", "").strip()
        if not clean_title or len(clean_title) > 120:
            raise KanbanError("Attachment title must contain 1 to 120 characters")
        content = await request.body()
        if len(content) > MAX_UPLOAD_BYTES:
            raise KanbanError("Uploads cannot exceed 10 MB")
        uploads.mkdir(parents=True, exist_ok=True)
        storage_name = str(uuid4())
        destination = uploads / storage_name
        destination.write_bytes(content)
        try:
            return board.add_attachment(card_id, kind="upload", title=clean_title,
                storage_name=storage_name,
                original_name=Path(request.headers.get("x-file-name", "upload")).name,
                media_type=request.headers.get("content-type"))
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    @application.patch("/api/attachments/{attachment_id}", response_model=AttachmentView)
    async def edit_attachment(attachment_id: str, value: AttachmentEdit,
        request: Request) -> AttachmentView:
        require_origin(request)
        return board.edit_attachment(attachment_id, value.title,
            str(value.url) if value.url is not None else None)

    @application.get("/api/attachments/{attachment_id}/content", response_class=Response,
        responses={200: {"content": {"application/octet-stream": {
            "schema": {"type": "string", "format": "binary"}}}}})
    async def attachment_content(attachment_id: str) -> Response:
        value = board.attachment(attachment_id)
        if value.kind != "upload" or value.storage_name is None:
            raise KanbanError("Attachment has no local content", "missing")
        path = uploads / value.storage_name
        if not path.is_file():
            raise KanbanError("Attachment content not found", "missing")
        filename = (value.original_name or "attachment").replace('"', "")
        return Response(path.read_bytes(), media_type=value.media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    @application.delete("/api/archive/{kind}/{identity}", status_code=status.HTTP_204_NO_CONTENT)
    async def archive(kind: str, identity: str, request: Request) -> None:
        require_origin(request)
        board.archive(kind, identity)

    @application.post("/api/archive/{kind}/{identity}/restore",
        status_code=status.HTTP_204_NO_CONTENT)
    async def restore(kind: str, identity: str, request: Request) -> None:
        require_origin(request)
        board.archive(kind, identity, restore=True)

    return application


app = create_app()
