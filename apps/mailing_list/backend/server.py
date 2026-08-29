"""FastAPI runtime for paid mailing-list enrollment."""

from pathlib import Path

from fastapi import FastAPI, Request
from pydantic import BaseModel

from apps.mailing_list.backend.database import Base, DomainError, MailingListRepository
from apps.mailing_list.backend.providers import SandboxGateway
from monotools.appkit import create_app_context
from monotools.http import domain_error_handler, enforce_same_origin
from monotools.runtime import create_application


DIRECTORY = Path(__file__).parent
DEFAULT_DATABASE = DIRECTORY / "data" / "mailing-list.db"
PRICE_MINOR = 500
CURRENCY = "usd"


class Enrollment(BaseModel):
    email: str = ""


class OfferingResponse(BaseModel):
    amount_minor: int
    currency: str
    interval: str
    payment_provider: str


class CheckoutResponse(BaseModel):
    checkout_id: str
    checkout_url: str
    provider: str


def create_app(database_url: str | None = None) -> FastAPI:
    context = create_app_context("mailing_list", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="MAILING_LIST_DATABASE_URL",
        database_url=database_url)
    repository = MailingListRepository(context.require_sessions(), SandboxGateway(), context.clock.now)
    application = create_application("mailing_list")
    application.add_exception_handler(DomainError, domain_error_handler(statuses={
        "forbidden": 403, "missing": 404,
    }))

    @application.get("/api/offering")
    def offering() -> OfferingResponse:
        return OfferingResponse(amount_minor=PRICE_MINOR, currency=CURRENCY,
            interval="month", payment_provider=repository.gateway.name)

    @application.post("/api/checkouts", status_code=201)
    def checkout(payload: Enrollment, request: Request) -> CheckoutResponse:
        enforce_same_origin(request, lambda message: DomainError(message, "forbidden"))
        base = str(request.base_url).rstrip("/")
        hosted = repository.begin_checkout(payload.email, PRICE_MINOR, CURRENCY,
            f"{base}/?checkout=success", f"{base}/?checkout=cancelled")
        return CheckoutResponse(checkout_id=hosted.external_id, checkout_url=hosted.url,
            provider=hosted.provider)

    return application


app = create_app()
