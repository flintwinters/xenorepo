"""Validated Kanban API contracts."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Priority = Literal["low", "normal", "high", "urgent"]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]


class BoardEdit(BaseModel):
    name: Name
    description: Text = ""
    default_priority: Priority = "normal"
    background_color: Color = "#1d2021"
    accent_color: Color = "#fabd2f"
    label_colors: dict[Name, Color] = {}


class BoardDetailsEdit(BaseModel):
    name: Name
    description: Text = ""
    default_priority: Priority = Field(default="normal", title="Default card priority")


class LabelColorEdit(BaseModel):
    color: Color


class ColumnCreate(BaseModel):
    name: Name = Field(title="Column name")
    color: Color = Field(default="#665c54", title="Column color")


class ColumnEdit(ColumnCreate):
    pass


class PositionInput(BaseModel):
    position: int


class CardFields(BaseModel):
    title: Name
    description: Text = ""
    assignee: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""
    labels: list[Name] = []
    priority: Priority = "normal"
    color: Color = "#32302f"

    @field_validator("labels")
    @classmethod
    def unique_labels(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result


class CardCreate(CardFields):
    column_id: str


class CardEdit(CardFields):
    pass


class CardMove(BaseModel):
    column_id: str
    position: int


class CommentInput(BaseModel):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)] = Field(
        title="Comment")


class LinkInput(BaseModel):
    title: Name
    url: HttpUrl


class AttachmentEdit(BaseModel):
    title: Name = Field(title="Attachment title")
    url: HttpUrl | None = Field(default=None, title="Web address")


class BoardView(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    default_priority: Priority
    background_color: Color
    accent_color: Color
    label_colors: dict[str, Color]


class ColumnView(BaseModel):
    id: str
    name: str
    position: int
    archived_at: datetime | None
    color: Color


class CardView(BaseModel):
    id: str
    column_id: str
    title: str
    description: str
    assignee: str
    labels: list[str]
    priority: Priority
    position: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    color: Color


class CommentView(BaseModel):
    id: str
    card_id: str
    body: str
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AttachmentView(BaseModel):
    id: str
    card_id: str
    kind: Literal["link", "upload"]
    title: str
    url: str | None
    original_name: str | None
    media_type: str | None
    archived_at: datetime | None
    created_at: datetime


class ActivityView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    subject_type: str
    subject_id: str
    summary: str
    occurred_at: datetime


class KanbanView(BaseModel):
    board: BoardView
    columns: list[ColumnView]
    cards: list[CardView]
    comments: list[CommentView]
    attachments: list[AttachmentView]
    activity: list[ActivityView]
