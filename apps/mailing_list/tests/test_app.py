"""Paid mailing-list domain and provider-contract tests."""

from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import func, select

from apps.mailing_list.backend.database import (
    Checkout, DomainError, MailingListRepository, PaymentEvent, Subscriber,
    create_session_factory,
)
from apps.mailing_list.backend.providers import SandboxGateway
from monotools.integrations.commerce import PaymentNotification
from monotools.integrations.mailer import Mail, SmtpMailer


class MailingListTests(unittest.TestCase):
    database = Path("apps/mailing_list/data/test-mailing-list.db")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.sessions = create_session_factory(f"sqlite:///{self.database}")
        self.repository = MailingListRepository(self.sessions, SandboxGateway(),
            lambda: datetime(2026, 8, 22, tzinfo=timezone.utc))

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    def test_checkout_normalizes_identity_and_retains_commercial_facts(self) -> None:
        hosted = self.repository.begin_checkout("  Reader@Example.COM ", 500, "USD",
            "https://app.test/success", "https://app.test/cancel")
        self.assertEqual(hosted.provider, "sandbox")
        with self.sessions() as session:
            subscriber = session.scalar(select(Subscriber))
            checkout = session.scalar(select(Checkout))
            self.assertEqual((subscriber.email, subscriber.state), ("reader@example.com", "pending"))
            self.assertEqual((checkout.amount_minor, checkout.currency, checkout.state), (500, "usd", "pending"))

    def test_paid_notification_is_idempotent_and_activates_subscriber(self) -> None:
        hosted = self.repository.begin_checkout("reader@example.com", 500, "usd", "ok", "cancel")
        notice = PaymentNotification("sandbox", "event-1", hosted.external_id, "paid")
        self.assertTrue(self.repository.apply_notification(notice))
        self.assertFalse(self.repository.apply_notification(notice))
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(Subscriber.state)), "active")
            self.assertEqual(session.scalar(select(Checkout.state)), "paid")
            self.assertEqual(session.scalar(select(func.count()).select_from(PaymentEvent)), 1)

    def test_invalid_or_unknown_payment_facts_fail_closed(self) -> None:
        with self.assertRaisesRegex(DomainError, "valid email"):
            self.repository.begin_checkout("not-an-email", 500, "usd", "ok", "cancel")
        with self.assertRaisesRegex(DomainError, "Checkout not found"):
            self.repository.apply_notification(PaymentNotification("sandbox", "event", "missing", "paid"))

    @patch("monotools.integrations.mailer.smtplib.SMTP")
    def test_smtp_adapter_owns_tls_authentication_and_message_transport(self, smtp: MagicMock) -> None:
        connection = smtp.return_value.__enter__.return_value
        connection.send_message.return_value = {}
        receipt = SmtpMailer("smtp.example.test", 587, username="dispatch",
            password="secret").send(Mail("news@example.test", "reader@example.test",
                "Edition one", "The durable issue body."))
        smtp.assert_called_once_with("smtp.example.test", 587, timeout=10)
        connection.starttls.assert_called_once()
        connection.login.assert_called_once_with("dispatch", "secret")
        sent = connection.send_message.call_args.args[0]
        self.assertEqual((sent["To"], sent["Subject"]),
            ("reader@example.test", "Edition one"))
        self.assertEqual(receipt.provider, "smtp")


if __name__ == "__main__":
    unittest.main()
