"""Define provider-neutral recurring-payment checkout contracts.

The request, result, event, and gateway protocols let monoapps retain commerce
facts while swapping hosted payment providers behind one narrow boundary.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CheckoutRequest:
    reference: str
    email: str
    amount_minor: int
    currency: str
    success_url: str
    cancel_url: str


@dataclass(frozen=True)
class HostedCheckout:
    provider: str
    external_id: str
    url: str


@dataclass(frozen=True)
class PaymentNotification:
    provider: str
    event_id: str
    external_checkout_id: str
    state: str


class PaymentGateway(Protocol):
    """The narrow surface an app needs from a recurring-payment provider."""

    name: str

    def create_checkout(self, request: CheckoutRequest) -> HostedCheckout: ...

    def parse_notification(self, payload: bytes, signature: str | None) -> PaymentNotification: ...
