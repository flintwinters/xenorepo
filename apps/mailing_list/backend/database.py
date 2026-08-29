"""Durable paid-subscriber facts and idempotent payment transitions."""

from collections.abc import Callable
from datetime import datetime
import re
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from monotools.runtime.appkit import SystemClock
from monotools.integrations.commerce import CheckoutRequest, HostedCheckout, PaymentGateway, PaymentNotification
from monotools.persistence.database import create_session_factory as _create_session_factory


EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class DomainError(ValueError):
    def __init__(self, message: str, kind: str = "validation") -> None:
        super().__init__(message)
        self.kind = kind


class Base(DeclarativeBase):
    pass


class Subscriber(Base):
    __tablename__ = "subscribers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Checkout(Base):
    __tablename__ = "checkouts"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="checkout_positive_amount"),
        UniqueConstraint("provider", "external_id", name="checkout_provider_external"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subscriber_id: Mapped[str] = mapped_column(ForeignKey("subscribers.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(255))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="payment_event_provider_external"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(255))
    checkout_id: Mapped[str] = mapped_column(ForeignKey("checkouts.id"), index=True)
    state: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    return _create_session_factory(database_url, Base.metadata)


class MailingListRepository:
    def __init__(self, sessions: sessionmaker[Session], gateway: PaymentGateway,
        clock: Callable[[], datetime] | None = None) -> None:
        self.sessions, self.gateway = sessions, gateway
        self.clock = clock or SystemClock().now

    def begin_checkout(self, email: str, amount_minor: int, currency: str,
        success_url: str, cancel_url: str) -> HostedCheckout:
        normalized = email.strip().casefold()
        if not EMAIL.fullmatch(normalized):
            raise DomainError("Enter a valid email address.")
        if amount_minor < 1 or len(currency) != 3:
            raise DomainError("The subscription price is invalid.")
        timestamp, subscriber_id, checkout_id = self.clock(), str(uuid4()), str(uuid4())
        with self.sessions.begin() as session:
            subscriber = session.scalar(select(Subscriber).where(Subscriber.email == normalized))
            if subscriber is None:
                subscriber = Subscriber(id=subscriber_id, email=normalized, state="pending",
                    created_at=timestamp, activated_at=None)
                session.add(subscriber)
                session.flush()
            checkout_id = str(uuid4())
            hosted = self.gateway.create_checkout(CheckoutRequest(checkout_id, normalized,
                amount_minor, currency.lower(), success_url, cancel_url))
            session.add(Checkout(id=checkout_id, subscriber_id=subscriber.id,
                provider=hosted.provider, external_id=hosted.external_id,
                amount_minor=amount_minor, currency=currency.lower(), state="pending",
                created_at=timestamp, paid_at=None))
        return hosted

    def apply_notification(self, notification: PaymentNotification) -> bool:
        if notification.state not in {"paid", "failed", "cancelled"}:
            raise DomainError("Unsupported payment state.")
        try:
            with self.sessions.begin() as session:
                checkout = session.scalar(select(Checkout).where(
                    Checkout.provider == notification.provider,
                    Checkout.external_id == notification.external_checkout_id))
                if checkout is None:
                    raise DomainError("Checkout not found.", "missing")
                timestamp = self.clock()
                session.add(PaymentEvent(provider=notification.provider,
                    external_id=notification.event_id, checkout_id=checkout.id,
                    state=notification.state, occurred_at=timestamp))
                checkout.state = notification.state
                if notification.state == "paid":
                    checkout.paid_at = timestamp
                    subscriber = session.get(Subscriber, checkout.subscriber_id)
                    subscriber.state, subscriber.activated_at = "active", timestamp
            return True
        except IntegrityError:
            return False
