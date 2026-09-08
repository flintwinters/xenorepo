"""Validated Kanban API contracts."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator, model_validator


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Color = Annotated[str, StringConstraints(pattern=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"),
    Field(json_schema_extra={"format": "color"})]


class BoardEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    description: Text = ""
    background_color: Color = "#1d2021"
    accent_color: Color = "#fabd2f"
    label_colors: dict[Name, Color] = {}


class BoardDetailsEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    description: Text = ""


class LabelColorEdit(BaseModel):
    color: Color = Field(title="Label color")


class ColumnCreate(BaseModel):
    name: Name = Field(title="Column name")
    color: Color = Field(default="#665c54", title="Column color")


class ColumnEdit(ColumnCreate):
    pass


class PositionInput(BaseModel):
    position: int


class CardFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Name
    assignee: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""
    labels: list[Name] = []
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


class LogInput(BaseModel):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)] = Field(
        title="Log entry")


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
    assignee: str
    labels: list[str]
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


class LogView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    card_id: str
    body: str
    created_at: datetime


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
    logs: list[LogView]
    comments: list[CommentView]
    attachments: list[AttachmentView]
    activity: list[ActivityView]


class ImportColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Name
    name: Name
    color: Color


class ImportCard(CardFields):
    model_config = ConfigDict(extra="forbid")
    id: Name
    column_id: Name


class ImportComment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card_id: Name
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ImportLog(ImportComment):
    created_at: datetime


class ImportAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card_id: Name
    kind: Literal["link", "upload"]
    title: Name
    url: HttpUrl | None
    original_name: str | None
    media_type: str | None

    @model_validator(mode="after")
    def importable_link(self) -> "ImportAttachment":
        if self.kind == "upload":
            raise ValueError("upload attachments cannot be imported without file content")
        if self.url is None:
            raise ValueError("link attachments require a URL")
        return self


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} IDs must be unique")


def _require_known(values: set[str], known: set[str], label: str) -> None:
    if missing := values - known:
        raise ValueError(f"{label} reference unknown parents: {', '.join(sorted(missing))}")


class BoardImport(BoardEdit):
    model_config = ConfigDict(extra="forbid")
    columns: list[ImportColumn]
    cards: list[ImportCard]
    logs: list[ImportLog]
    comments: list[ImportComment]
    attachments: list[ImportAttachment]

    @model_validator(mode="after")
    def valid_relationships(self) -> "BoardImport":
        column_ids = [value.id for value in self.columns]
        card_ids = [value.id for value in self.cards]
        _require_unique(column_ids, "column")
        _require_unique(card_ids, "card")
        _require_known({value.column_id for value in self.cards}, set(column_ids), "cards")
        _require_known({value.card_id for value in [*self.logs, *self.comments, *self.attachments]},
            set(card_ids), "children")
        return self


class ImportResult(BaseModel):
    mode: Literal["append", "replace"]
    columns: int
    cards: int
    logs: int
    comments: int
    attachments: int
