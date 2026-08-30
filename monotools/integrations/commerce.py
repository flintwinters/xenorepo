"""Define provider-neutral hosted-payment checkout contracts.

The request, result, event, and gateway protocols let monoapps retain commerce
facts while swapping hosted payment providers behind one narrow boundary.
"""

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class OneTimeTerms:
    amount_minor: int
    currency: str


@dataclass(frozen=True)
class RecurringTerms:
    amount_minor: int
    currency: str
    interval: Literal["day", "week", "month", "year"]
    interval_count: int = 1


CheckoutTerms = OneTimeTerms | RecurringTerms


@dataclass(frozen=True)
class CheckoutRequest:
    reference: str
    email: str
    terms: CheckoutTerms
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
    """The narrow surface an app needs from a hosted-payment provider."""

    name: str

    def create_checkout(self, request: CheckoutRequest) -> HostedCheckout: ...

    def parse_notification(self, payload: bytes, signature: str | None) -> PaymentNotification: ...
