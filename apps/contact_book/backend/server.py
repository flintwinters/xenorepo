"""FastAPI runtime for Contact Book."""

from pathlib import Path

from fastapi import FastAPI, Query, Request, status

from apps.contact_book.backend.database import (
    Base, Contact, ContactCreate, ContactError, ContactPage, ContactStore, ContactUpdate,
    Direction, SortField,
)
from monotools.runtime.appkit import create_app_context
from monotools.runtime.application import create_local_application
from monotools.runtime.http import domain_error_handler, enforce_same_origin

DEFAULT_DATABASE = Path(__file__).parent.parent / "data" / "contacts.db"


def create_app(database_url: str | None = None, store: ContactStore | None = None) -> FastAPI:
    context = create_app_context("contact_book", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="CONTACT_BOOK_DATABASE_URL",
        database_url=database_url)
    contacts = store or ContactStore(context.require_sessions(), now=context.clock.now)
    application = create_local_application(__file__)
    application.state.contacts = contacts
    application.add_exception_handler(ContactError, domain_error_handler(statuses={
        "conflict": 409, "forbidden": 403, "missing": 404, "validation": 422,
    }))

    def require_origin(request: Request) -> None:
        enforce_same_origin(request, lambda message: ContactError(message, "forbidden"))

    @application.get("/api/contacts", response_model=ContactPage)
    async def list_contacts(q: str = Query("", max_length=160), sort: SortField = "name",
        direction: Direction = "asc", page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100)) -> ContactPage:
        return contacts.list(query=q, sort=sort, direction=direction, page=page, page_size=page_size)

    @application.post("/api/contacts", response_model=Contact, status_code=status.HTTP_201_CREATED,
        operation_id="create_contact")
    async def create_contact(value: ContactCreate, request: Request) -> Contact:
        require_origin(request)
        return contacts.create(value)

    @application.put("/api/contacts/{contact_id}", response_model=Contact,
        operation_id="update_contact")
    async def update_contact(contact_id: str, value: ContactUpdate, request: Request) -> Contact:
        require_origin(request)
        contact = contacts.update(contact_id, value)
        if contact is None:
            raise ContactError("Contact not found", "missing")
        return contact

    @application.delete("/api/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_contact")
    async def delete_contact(contact_id: str, request: Request) -> None:
        require_origin(request)
        if not contacts.delete(contact_id):
            raise ContactError("Contact not found", "missing")

    return application


app = create_app()
