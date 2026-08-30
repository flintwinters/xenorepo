"""FastAPI runtime for paid mailing-list enrollment."""

from pathlib import Path

from fastapi import FastAPI, Header, Request
from pydantic import BaseModel

from apps.mailing_list.backend.database import Base, DomainError, MailingListRepository
from apps.mailing_list.backend.providers import SandboxGateway
from monotools.integrations.commerce import PaymentGateway
from monotools.runtime.appkit import create_app_context
from monotools.runtime.http import domain_error_handler, enforce_same_origin
from monotools.runtime.application import create_application


DIRECTORY = Path(__file__).parent.parent
DEFAULT_DATABASE = DIRECTORY / "data" / "mailing-list.db"
PRICE_MINOR = 500
CURRENCY = "usd"
SANDBOX_SECRET = "dispatch-ledger-local-sandbox"


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
    repeated: bool = False


def create_app(database_url: str | None = None, gateway: PaymentGateway | None = None) -> FastAPI:
    context = create_app_context("mailing_list", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="MAILING_LIST_DATABASE_URL",
        database_url=database_url)
    payment_gateway = gateway or SandboxGateway(SANDBOX_SECRET)
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
            f"{base}/?checkout=success", f"{base}/?checkout=cancelled")
        return CheckoutResponse(checkout_id=hosted.external_id, checkout_url=hosted.url,
            provider=hosted.provider)

    @application.get("/api/checkouts/{checkout_id}")
    def checkout_status(checkout_id: str) -> CheckoutStatusResponse:
        status = repository.checkout_status(payment_gateway.name, checkout_id)
        return CheckoutStatusResponse(checkout_id=status.checkout_id, state=status.state)

    async def accept_notification(request: Request, signature: str | None) -> CheckoutStatusResponse:
        try:
            notification = payment_gateway.parse_notification(await request.body(), signature)
        except ValueError as error:
            raise DomainError(str(error), "forbidden") from error
        changed = repository.apply_notification(notification)
        status = repository.checkout_status(notification.provider,
            notification.external_checkout_id)
        return CheckoutStatusResponse(checkout_id=status.checkout_id, state=status.state,
            repeated=not changed)

    @application.post("/api/webhooks/payments/sandbox")
    async def sandbox_webhook(request: Request,
        x_payment_signature: str | None = Header(default=None)) -> CheckoutStatusResponse:
        return await accept_notification(request, x_payment_signature)

    @application.post("/api/sandbox/checkouts/{checkout_id}/{state}")
    async def complete_sandbox(checkout_id: str, state: str, request: Request) -> CheckoutStatusResponse:
        enforce_same_origin(request, lambda message: DomainError(message, "forbidden"))
        if not isinstance(payment_gateway, SandboxGateway) or state not in {"paid", "cancelled"}:
            raise DomainError("Sandbox checkout action is unavailable.", "missing")
        payload, signature = payment_gateway.notification(checkout_id, state)
        notification = payment_gateway.parse_notification(payload, signature)
        changed = repository.apply_notification(notification)
        status = repository.checkout_status(payment_gateway.name, checkout_id)
        return CheckoutStatusResponse(checkout_id=status.checkout_id, state=status.state,
            repeated=not changed)

    return application


app = create_app()
