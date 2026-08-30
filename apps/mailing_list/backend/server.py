"""FastAPI runtime for paid mailing-list enrollment."""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from apps.mailing_list.backend.database import Base, DomainError, MailingListRepository
from apps.mailing_list.backend.providers import SANDBOX_SECRET, SandboxGateway, configured_gateway
from monotools.integrations.commerce import PaymentGateway
from monotools.runtime.appkit import create_app_context
from monotools.runtime.http import domain_error_handler, enforce_same_origin
from monotools.runtime.application import create_application


DIRECTORY = Path(__file__).parent.parent
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


class CheckoutStatusResponse(BaseModel):
    checkout_id: str
    state: str
    provider: str
    created_at: datetime
    paid_at: datetime | None
    event_count: int
    last_event_at: datetime | None
    repeated: bool = False


def create_app(database_url: str | None = None, gateway: PaymentGateway | None = None) -> FastAPI:
    context = create_app_context("mailing_list", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="MAILING_LIST_DATABASE_URL",
        database_url=database_url)
    payment_gateway = gateway or configured_gateway()
    repository = MailingListRepository(context.require_sessions(), payment_gateway, context.clock.now)
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
            f"{base}/?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            f"{base}/?checkout=cancelled")
        return CheckoutResponse(checkout_id=hosted.external_id, checkout_url=hosted.url,
            provider=hosted.provider)

    @application.get("/api/checkouts/{checkout_id}")
    def checkout_status(checkout_id: str) -> CheckoutStatusResponse:
        status = repository.checkout_status(payment_gateway.name, checkout_id)
        return CheckoutStatusResponse(**asdict(status))

    async def accept_notification(request: Request, signature: str | None):
        try:
            notification = payment_gateway.parse_notification(await request.body(), signature)
        except ValueError as error:
            raise DomainError(str(error), "forbidden") from error
        if notification is None:
            return Response(status_code=204)
        changed = repository.apply_notification(notification)
        status = repository.checkout_status(notification.provider,
            notification.external_checkout_id)
        return CheckoutStatusResponse(**asdict(status), repeated=not changed)

    @application.post("/api/webhooks/payments/{provider}", response_model=None)
    async def payment_webhook(provider: str, request: Request):
        if provider != payment_gateway.name:
            raise DomainError("Payment provider is unavailable.", "missing")
        return await accept_notification(request,
            request.headers.get(payment_gateway.signature_header))

    @application.post("/api/sandbox/checkouts/{checkout_id}/{state}")
    async def complete_sandbox(checkout_id: str, state: str, request: Request) -> CheckoutStatusResponse:
        enforce_same_origin(request, lambda message: DomainError(message, "forbidden"))
        if not isinstance(payment_gateway, SandboxGateway) or state not in {"paid", "cancelled"}:
            raise DomainError("Sandbox checkout action is unavailable.", "missing")
        payload, signature = payment_gateway.notification(checkout_id, state)
        notification = payment_gateway.parse_notification(payload, signature)
        if notification is None:
            raise RuntimeError("Sandbox settlement did not produce a payment notification.")
        changed = repository.apply_notification(notification)
        status = repository.checkout_status(payment_gateway.name, checkout_id)
        return CheckoutStatusResponse(**asdict(status), repeated=not changed)

    return application


app = create_app()
