"""Durable single-calendar domain model and operations."""

from __future__ import annotations

from datetime import UTC, date as LocalDate, datetime, time
from typing import Annotated, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError, model_validator
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Index, Integer, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class CalendarError(ValueError):
    def __init__(self, message: str, kind: str = "validation") -> None:
        super().__init__(message)
        self.kind = kind


class TimeZoneInput(BaseModel):
    time_zone: str

    @model_validator(mode="after")
    def valid_iana_zone(self) -> TimeZoneInput:
        try:
            ZoneInfo(self.time_zone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("time_zone must be a valid IANA timezone") from error
        return self


class EventFields(BaseModel):
    title: Title
    date: LocalDate
    all_day: bool
    start_time: time | None = None
    end_time: time | None = None
    location: OptionalText | None = None
    notes: OptionalText | None = None

    @model_validator(mode="after")
    def valid_interval(self) -> EventFields:
        if self.all_day and (self.start_time is not None or self.end_time is not None):
            raise ValueError("All-day events cannot have times")
        if not self.all_day and (self.start_time is None or self.end_time is None):
            raise ValueError("Timed events require both start_time and end_time")
        if self.start_time is not None and self.end_time is not None and self.start_time >= self.end_time:
            raise ValueError("end_time must be later than start_time")
        return self


class EventCreate(EventFields):
    pass


class EventUpdate(BaseModel):
    title: Title | None = None
    date: LocalDate | None = None
    all_day: bool | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: OptionalText | None = None
    notes: OptionalText | None = None

    @model_validator(mode="after")
    def require_update(self) -> EventUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one event field must be updated")
        return self


class Event(EventFields):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class CalendarView(BaseModel):
    time_zone: str | None
    events: list[Event]


class Base(DeclarativeBase):
    pass


class CalendarSettings(Base):
    __tablename__ = "calendar_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_calendar_settings"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    time_zone: Mapped[str] = mapped_column(String(100), unique=True)
    initialized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventRecord(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint(
            "(all_day = 1 AND start_minute IS NULL AND end_minute IS NULL) OR "
            "(all_day = 0 AND start_minute IS NOT NULL AND end_minute IS NOT NULL "
            "AND start_minute >= 0 AND end_minute <= 1440 AND start_minute < end_minute)",
            name="event_time_shape",
        ),
        Index("event_date_order", "event_date", "all_day", "start_minute", "title", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    event_date: Mapped[LocalDate] = mapped_column(Date, index=True)
    all_day: Mapped[bool] = mapped_column(Boolean)
    start_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _minute(value: time | None) -> int | None:
    return None if value is None else value.hour * 60 + value.minute


def _time(value: int | None) -> time | None:
    return None if value is None else time(value // 60, value % 60)


def _event(record: EventRecord) -> Event:
    return Event(id=record.id, title=record.title, date=record.event_date,
        all_day=record.all_day, start_time=_time(record.start_minute),
        end_time=_time(record.end_minute), location=record.location, notes=record.notes,
        created_at=record.created_at, updated_at=record.updated_at)


class CalendarStore:
    """Transactional authority for settings and events."""

    def __init__(self, sessions: sessionmaker[Session],
        now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.sessions = sessions
        self.now = now

    def initialize_time_zone(self, value: str) -> str:
        TimeZoneInput(time_zone=value)
        with self.sessions.begin() as session:
            settings = session.get(CalendarSettings, 1)
            if settings is None:
                session.add(CalendarSettings(id=1, time_zone=value, initialized_at=self.now()))
                return value
            if settings.time_zone != value:
                raise CalendarError("Calendar timezone is already initialized", "conflict")
            return settings.time_zone

    def view(self, start: LocalDate, end: LocalDate) -> CalendarView:
        if start >= end:
            raise CalendarError("end must be later than start")
        with self.sessions() as session:
            zone = session.get(CalendarSettings, 1)
            records = session.scalars(select(EventRecord).where(
                EventRecord.event_date >= start, EventRecord.event_date < end).order_by(
                    EventRecord.event_date, EventRecord.all_day.desc(),
                    EventRecord.start_minute, EventRecord.title, EventRecord.id)).all()
            return CalendarView(time_zone=zone.time_zone if zone else None,
                events=[_event(record) for record in records])

    def create(self, request: EventCreate) -> Event:
        now = self.now()
        record = EventRecord(id=str(uuid4()), title=request.title, event_date=request.date,
            all_day=request.all_day, start_minute=_minute(request.start_time),
            end_minute=_minute(request.end_time), location=request.location or None,
            notes=request.notes or None, created_at=now, updated_at=now)
        with self.sessions.begin() as session:
            session.add(record)
        return _event(record)

    def update(self, event_id: str, update: EventUpdate) -> Event | None:
        with self.sessions.begin() as session:
            record = session.get(EventRecord, event_id)
            if record is None:
                return None
            current = EventFields(title=record.title, date=record.event_date,
                all_day=record.all_day, start_time=_time(record.start_minute),
                end_time=_time(record.end_minute), location=record.location, notes=record.notes)
            try:
                merged = EventFields.model_validate(current.model_dump() | update.model_dump(
                    exclude_unset=True))
            except ValidationError as error:
                message = error.errors()[0].get("ctx", {}).get("error", error)
                raise CalendarError(str(message)) from error
            record.title = merged.title
            record.event_date = merged.date
            record.all_day = merged.all_day
            record.start_minute = _minute(merged.start_time)
            record.end_minute = _minute(merged.end_time)
            record.location = merged.location or None
            record.notes = merged.notes or None
            record.updated_at = self.now()
            session.flush()
            result = _event(record)
        return result

    def delete(self, event_id: str) -> bool:
        with self.sessions.begin() as session:
            record = session.get(EventRecord, event_id)
            if record is None:
                return False
            session.delete(record)
        return True
