"""Translate generic hosted-checkout contracts to Stripe Checkout.

The adapter owns Stripe request shape, idempotency, and signed snapshot-event
interpretation while applications and generic commerce contracts remain free
of provider vocabulary.
"""

from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

import stripe

from monotools.integrations.commerce import (
    CheckoutRequest, HostedCheckout, PaymentNotification, RecurringTerms,
)


class SessionCreator(Protocol):
    def create(
        self, params: Mapping[str, object], options: Mapping[str, object] | None = None
    ) -> object: ...


class StripeGateway:
    """Create Stripe-hosted checkouts and authenticate their snapshot events."""

    name = "stripe"
    signature_header = "stripe-signature"
    _states = {
        "checkout.session.async_payment_failed": "failed",
        "checkout.session.async_payment_succeeded": "paid",
        "checkout.session.expired": "cancelled",
    }

    def __init__(self, api_key: str, webhook_secret: str, *,
        sessions: SessionCreator | None = None,
        construct_event: Callable[[bytes, str | None, str], object] | None = None) -> None:
        if not api_key or not webhook_secret:
            raise ValueError("Stripe API and webhook secrets are required.")
        client = stripe.StripeClient(api_key)
        self._sessions = sessions or cast(SessionCreator, client.v1.checkout.sessions)
        self._construct_event = construct_event or stripe.Webhook.construct_event
        self._webhook_secret = webhook_secret

    def create_checkout(self, request: CheckoutRequest) -> HostedCheckout:
        recurring = isinstance(request.terms, RecurringTerms)
        price_data: dict[str, object] = {
            "currency": request.terms.currency,
            "product_data": {"name": request.label},
            "unit_amount": request.terms.amount_minor,
        }
        if recurring:
            price_data["recurring"] = {
                "interval": request.terms.interval,
                "interval_count": request.terms.interval_count,
            }
        params: dict[str, object] = {
            "cancel_url": request.cancel_url,
            "client_reference_id": request.reference,
            "customer_email": request.email,
            "line_items": [{"price_data": price_data, "quantity": 1}],
            "metadata": {"reference": request.reference},
            "mode": "subscription" if recurring else "payment",
            "success_url": request.success_url,
        }
        session = self._sessions.create(params, {"idempotency_key": request.reference})
        identifier, url = self._field(session, "id"), self._field(session, "url")
        if not isinstance(identifier, str) or not isinstance(url, str):
            raise RuntimeError("Stripe returned an incomplete Checkout Session.")
        return HostedCheckout(self.name, identifier, url)

    def parse_notification(
        self, payload: bytes, signature: str | None
    ) -> PaymentNotification | None:
        try:
            event = self._construct_event(payload, signature, self._webhook_secret)
            event_type = self._field(event, "type")
            event_id = self._field(event, "id")
            data = self._field(event, "data")
            session = self._field(data, "object")
            checkout_id = self._field(session, "id")
        except (AttributeError, KeyError, TypeError, ValueError,
            stripe.SignatureVerificationError) as error:
            raise ValueError("Invalid Stripe webhook.") from error
        if not isinstance(event_type, str):
            raise ValueError("Invalid Stripe webhook.")
        if event_type == "checkout.session.completed":
            payment_status = self._field(session, "payment_status")
            if payment_status not in {"paid", "no_payment_required"}:
                return None
            state = "paid"
        else:
            state = self._states.get(event_type)
            if state is None:
                return None
        if not isinstance(event_id, str) or not isinstance(checkout_id, str):
            raise ValueError("Invalid Stripe webhook.")
        return PaymentNotification(self.name, event_id, checkout_id, state)

    @staticmethod
    def _field(value: object, name: str) -> Any:
        if isinstance(value, Mapping):
            return value[name]
        return getattr(value, name)
