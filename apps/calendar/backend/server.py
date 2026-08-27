"""FastAPI runtime for Calendar Console."""

from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request, status

from apps.calendar.backend.database import (
    Base, CalendarError, CalendarStore, CalendarView, Event, EventCreate, EventUpdate, TimeZoneInput,
)
from monotools.appkit import create_app_context
from monotools.http import domain_error_handler, enforce_same_origin
from monotools.runtime import create_application


DEFAULT_DATABASE = Path(__file__).parent.parent / "data" / "calendar.db"


def create_app(database_url: str | None = None, store: CalendarStore | None = None) -> FastAPI:
    context = create_app_context("calendar", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="CALENDAR_DATABASE_URL",
        database_url=database_url)
    calendar = store or CalendarStore(context.require_sessions(), now=context.clock.now)
    application = create_application("calendar")
    application.state.calendar = calendar
    application.add_exception_handler(CalendarError, domain_error_handler(statuses={
        "conflict": 409, "forbidden": 403, "missing": 404, "validation": 422,
    }))

    def require_origin(request: Request) -> None:
        enforce_same_origin(request, lambda message: CalendarError(message, "forbidden"))

    @application.get("/api/calendar", response_model=CalendarView)
    async def get_calendar(start: date, end: date) -> CalendarView:
        return calendar.view(start, end)

    @application.put("/api/settings/time-zone")
    async def initialize_time_zone(value: TimeZoneInput, request: Request) -> dict[str, str]:
        require_origin(request)
        return {"time_zone": calendar.initialize_time_zone(value.time_zone)}

    @application.post("/api/events", response_model=Event, status_code=status.HTTP_201_CREATED)
    async def create_event(value: EventCreate, request: Request) -> Event:
        require_origin(request)
        return calendar.create(value)

    @application.patch("/api/events/{event_id}", response_model=Event)
    async def update_event(event_id: str, value: EventUpdate, request: Request) -> Event:
        require_origin(request)
        event = calendar.update(event_id, value)
        if event is None:
            raise CalendarError("Event not found", "missing")
        return event

    @application.delete("/api/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_event(event_id: str, request: Request) -> None:
        require_origin(request)
        if not calendar.delete(event_id):
            raise CalendarError("Event not found", "missing")

    return application


app = create_app()
