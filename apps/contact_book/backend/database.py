"""Durable contacts and deterministic directory queries."""

from datetime import UTC, datetime
from typing import Annotated, Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import DateTime, Index, String, Text, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Email = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254,
    pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]
SortField = Literal["name", "email", "company", "job_title", "city"]
Direction = Literal["asc", "desc"]


class ContactError(ValueError):
    def __init__(self, message: str, kind: str = "validation") -> None:
        super().__init__(message)
        self.kind = kind


class ContactFields(BaseModel):
    name: RequiredText
    email: Email
    phone: OptionalText | None = None
    company: OptionalText | None = None
    job_title: OptionalText | None = None
    city: OptionalText | None = None
    tags: list[RequiredText] = []


class ContactCreate(ContactFields):
    pass


class ContactUpdate(ContactFields):
    pass


class Contact(ContactFields):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class ContactPage(BaseModel):
    items: list[Contact]
    page: int
    page_size: int
    total: int
    pages: int


class Base(DeclarativeBase):
    pass


class ContactRecord(Base):
    __tablename__ = "contacts"
    __table_args__ = (Index("contact_name_order", "name", "id"),
        Index("contact_company_order", "company", "id"),
        Index("contact_job_title_order", "job_title", "id"),
        Index("contact_city_order", "city", "id"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(160), nullable=True)
    company: Mapped[str | None] = mapped_column(String(160), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    city: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tags_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _contact(record: ContactRecord) -> Contact:
    return Contact(id=record.id, name=record.name, email=record.email, phone=record.phone,
        company=record.company, job_title=record.job_title, city=record.city,
        tags=[value for value in record.tags_text.split("\n") if value],
        created_at=record.created_at, updated_at=record.updated_at)


def _normalized(value: ContactFields) -> dict[str, object]:
    fields = value.model_dump()
    fields["email"] = value.email.casefold()
    fields["tags_text"] = "\n".join(dict.fromkeys(tag.casefold() for tag in value.tags))
    del fields["tags"]
    return fields


class ContactStore:
    def __init__(self, sessions: sessionmaker[Session],
        now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.sessions = sessions
        self.now = now

    def list(self, *, query: str = "", sort: SortField = "name", direction: Direction = "asc",
        page: int = 1, page_size: int = 25) -> ContactPage:
        term = query.strip()
        statement = select(ContactRecord)
        count_statement = select(func.count()).select_from(ContactRecord)
        if term:
            pattern = f"%{term}%"
            predicate = or_(*[column.ilike(pattern) for column in (ContactRecord.name,
                ContactRecord.email, ContactRecord.company, ContactRecord.job_title,
                ContactRecord.city, ContactRecord.tags_text)])
            statement, count_statement = statement.where(predicate), count_statement.where(predicate)
        column = getattr(ContactRecord, sort)
        ordering = column.desc() if direction == "desc" else column.asc()
        with self.sessions() as session:
            total = session.scalar(count_statement) or 0
            records = session.scalars(statement.order_by(ordering, ContactRecord.id)
                .offset((page - 1) * page_size).limit(page_size)).all()
        return ContactPage(items=[_contact(record) for record in records], page=page,
            page_size=page_size, total=total, pages=max(1, (total + page_size - 1) // page_size))

    def create(self, value: ContactCreate, *, identity: str | None = None) -> Contact:
        instant = self.now()
        record = ContactRecord(id=identity or str(uuid4()), **_normalized(value),
            created_at=instant, updated_at=instant)
        try:
            with self.sessions.begin() as session:
                session.add(record)
        except IntegrityError as error:
            raise ContactError("A contact with that email already exists", "conflict") from error
        return _contact(record)

    def update(self, contact_id: str, value: ContactUpdate) -> Contact | None:
        try:
            with self.sessions.begin() as session:
                record = session.get(ContactRecord, contact_id)
                if record is None:
                    return None
                for name, field in _normalized(value).items():
                    setattr(record, name, field)
                record.updated_at = self.now()
                session.flush()
                result = _contact(record)
        except IntegrityError as error:
            raise ContactError("A contact with that email already exists", "conflict") from error
        return result

    def delete(self, contact_id: str) -> bool:
        with self.sessions.begin() as session:
            record = session.get(ContactRecord, contact_id)
            if record is None:
                return False
            session.delete(record)
        return True
