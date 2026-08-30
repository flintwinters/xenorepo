"""Paid mailing-list domain and provider-contract tests."""

from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from apps.mailing_list.backend.database import (
    Checkout, DomainError, MailingListRepository, PaymentEvent, Subscriber,
    create_session_factory,
)
from apps.mailing_list.backend.providers import (
    SANDBOX_SECRET, STRIPE_API_KEY, STRIPE_WEBHOOK_KEY, SandboxGateway, configured_gateway,
)
from apps.mailing_list.backend.server import DEFAULT_DATABASE, create_app
from monotools.integrations.commerce import HostedCheckout, PaymentNotification, RecurringTerms
from monotools.integrations.mailer import Mail, SmtpMailer
from monotools.integrations.stripe import StripeGateway


class MailingListTests(unittest.TestCase):
    database = Path("apps/mailing_list/data/test-mailing-list.db")

    def setUp(self) -> None:
        self.database.unlink(missing_ok=True)
        self.sessions = create_session_factory(f"sqlite:///{self.database}")
        self.repository = MailingListRepository(self.sessions, SandboxGateway(SANDBOX_SECRET),
            lambda: datetime(2026, 8, 22, tzinfo=timezone.utc))

    def tearDown(self) -> None:
        self.sessions.kw["bind"].dispose()
        self.database.unlink(missing_ok=True)

    def test_default_database_uses_the_app_owned_data_directory(self) -> None:
        self.assertEqual(DEFAULT_DATABASE, Path("apps/mailing_list/data/mailing-list.db").resolve())

    def test_gateway_configuration_is_complete_or_safely_sandboxed(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsInstance(configured_gateway(), SandboxGateway)
        with patch.dict("os.environ", {STRIPE_API_KEY: "sk_test_configured"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, STRIPE_WEBHOOK_KEY):
                configured_gateway()
        configured = {STRIPE_API_KEY: "sk_test_configured", STRIPE_WEBHOOK_KEY: "whsec_test"}
        with patch.dict("os.environ", configured, clear=True):
            self.assertIsInstance(configured_gateway(), StripeGateway)

    def test_checkout_normalizes_identity_and_retains_commercial_facts(self) -> None:
        hosted = self.repository.begin_checkout("  Reader@Example.COM ", 500, "USD",
            "https://app.test/success", "https://app.test/cancel")
        self.assertEqual(hosted.provider, "sandbox")
        with self.sessions() as session:
            subscriber = session.scalar(select(Subscriber))
            checkout = session.scalar(select(Checkout))
            self.assertEqual((subscriber.email, subscriber.state), ("reader@example.com", "pending"))
            self.assertEqual((checkout.amount_minor, checkout.currency, checkout.state), (500, "usd", "pending"))

    def test_mailing_list_requests_monthly_recurring_checkout_terms(self) -> None:
        gateway = MagicMock()
        gateway.name = "capture"
        gateway.create_checkout.return_value = HostedCheckout("capture", "external", "https://pay.test")
        repository = MailingListRepository(self.sessions, gateway, self.repository.clock)
        repository.begin_checkout("reader@example.com", 500, "USD", "success", "cancel")
        request = gateway.create_checkout.call_args.args[0]
        self.assertEqual(request.terms, RecurringTerms(500, "usd", "month"))

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

    def test_public_sandbox_lifecycle_authenticates_and_replays_safely(self) -> None:
        app_database = Path("apps/mailing_list/data/test-mailing-list-api.db")
        app_database.unlink(missing_ok=True)
        try:
            with TestClient(create_app(f"sqlite:///{app_database}")) as client:
                created = client.post("/api/checkouts", json={"email": "reader@example.test"})
                self.assertEqual(created.status_code, 201)
                checkout_id = created.json()["checkout_id"]
                pending = client.get(f"/api/checkouts/{checkout_id}")
                self.assertEqual(pending.json()["state"], "pending")

                rejected = client.post("/api/webhooks/payments/sandbox", content=b"{}",
                    headers={"x-payment-signature": "incorrect"})
                self.assertEqual(rejected.status_code, 403)
                payload, signature = SandboxGateway(SANDBOX_SECRET).notification(checkout_id, "paid")
                paid = client.post("/api/webhooks/payments/sandbox", content=payload,
                    headers={"x-payment-signature": signature})
                self.assertEqual(paid.json()["state"], "paid")
                replay = client.post("/api/webhooks/payments/sandbox", content=payload,
                    headers={"x-payment-signature": signature})
                self.assertEqual(replay.json()["repeated"], True)

                invalid = client.post("/api/checkouts", json={"email": "not-an-email"})
                self.assertEqual(invalid.status_code, 400)
                self.assertEqual(invalid.json(), {"error": "Enter a valid email address."})
        finally:
            app_database.unlink(missing_ok=True)

    def test_public_webhook_uses_the_gateway_signature_contract_and_ignores_noise(self) -> None:
        app_database = Path("apps/mailing_list/data/test-mailing-list-stripe-api.db")
        app_database.unlink(missing_ok=True)
        gateway = MagicMock()
        gateway.name, gateway.signature_header = "stripe", "stripe-signature"
        gateway.create_checkout.return_value = HostedCheckout(
            "stripe", "cs_live_return", "https://checkout.stripe.test/session")
        gateway.parse_notification.return_value = None
        try:
            with TestClient(create_app(f"sqlite:///{app_database}", gateway)) as client:
                created = client.post("/api/checkouts", json={"email": "reader@example.test"})
                self.assertEqual(created.status_code, 201)
                request = gateway.create_checkout.call_args.args[0]
                self.assertIn("session_id={CHECKOUT_SESSION_ID}", request.success_url)
                ignored = client.post("/api/webhooks/payments/stripe", content=b"event",
                    headers={"stripe-signature": "signed"})
                self.assertEqual(ignored.status_code, 204)
                gateway.parse_notification.assert_called_once_with(b"event", "signed")
                missing = client.post("/api/webhooks/payments/sandbox", content=b"event")
                self.assertEqual(missing.status_code, 404)
        finally:
            app_database.unlink(missing_ok=True)

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
