"""Provider-neutral commerce terms and Stripe adapter contract tests."""

import json
import unittest
from unittest.mock import MagicMock

from stripe import WebhookSignature

from monotools.integrations.commerce import CheckoutRequest, OneTimeTerms, RecurringTerms
from monotools.integrations.stripe import StripeGateway


class StripeGatewayTests(unittest.TestCase):
    secret = "whsec_contract_test"

    def gateway(self, sessions: MagicMock | None = None) -> StripeGateway:
        return StripeGateway("sk_test_contract", self.secret, sessions=sessions or MagicMock())

    @staticmethod
    def request(terms: OneTimeTerms | RecurringTerms) -> CheckoutRequest:
        return CheckoutRequest("order-17", "reader@example.test", "Field notes", terms,
            "https://app.test/success", "https://app.test/cancel")

    def test_one_time_checkout_maps_to_payment_mode_and_is_idempotent(self) -> None:
        sessions = MagicMock()
        sessions.create.return_value = {"id": "cs_payment", "url": "https://checkout.stripe.test/pay"}
        checkout = self.gateway(sessions).create_checkout(
            self.request(OneTimeTerms(900, "usd")))
        params, options = sessions.create.call_args.args
        self.assertEqual(params["mode"], "payment")
        self.assertNotIn("recurring", params["line_items"][0]["price_data"])
        self.assertEqual(options, {"idempotency_key": "order-17"})
        self.assertEqual((checkout.provider, checkout.external_id), ("stripe", "cs_payment"))

    def test_subscription_checkout_maps_interval_without_provider_leakage(self) -> None:
        sessions = MagicMock()
        sessions.create.return_value = {"id": "cs_subscription", "url": "https://checkout.stripe.test/sub"}
        self.gateway(sessions).create_checkout(
            self.request(RecurringTerms(500, "usd", "month", 1)))
        params = sessions.create.call_args.args[0]
        price = params["line_items"][0]["price_data"]
        self.assertEqual(params["mode"], "subscription")
        self.assertEqual(price["recurring"], {"interval": "month", "interval_count": 1})
        self.assertEqual(price["product_data"], {"name": "Field notes"})

    def test_signed_checkout_events_normalize_terminal_states(self) -> None:
        cases = {
            "checkout.session.completed": ("paid", "paid"),
            "checkout.session.async_payment_succeeded": ("unpaid", "paid"),
            "checkout.session.async_payment_failed": ("unpaid", "failed"),
            "checkout.session.expired": ("unpaid", "cancelled"),
        }
        for event_type, (payment_status, expected) in cases.items():
            with self.subTest(event_type=event_type):
                payload = json.dumps({"id": f"evt-{expected}", "object": "event",
                    "type": event_type, "data": {"object": {
                        "id": "cs_checkout", "payment_status": payment_status}}})
                signature = WebhookSignature.generate_signature_header(payload, self.secret)
                notice = self.gateway().parse_notification(payload.encode(), signature)
                self.assertEqual((notice.provider, notice.external_checkout_id, notice.state),
                    ("stripe", "cs_checkout", expected))

    def test_incomplete_and_unrelated_events_are_acknowledged_without_transition(self) -> None:
        for event_type, payment_status in [
            ("checkout.session.completed", "unpaid"), ("customer.created", None),
        ]:
            payload = json.dumps({"id": "evt-ignored", "object": "event", "type": event_type,
                "data": {"object": {"id": "cs_checkout", "payment_status": payment_status}}})
            signature = WebhookSignature.generate_signature_header(payload, self.secret)
            self.assertIsNone(self.gateway().parse_notification(payload.encode(), signature))

    def test_invalid_signature_and_incomplete_session_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid Stripe webhook"):
            self.gateway().parse_notification(b"{}", "invalid")
        sessions = MagicMock()
        sessions.create.return_value = {"id": "cs_missing_url", "url": None}
        with self.assertRaisesRegex(RuntimeError, "incomplete Checkout Session"):
            self.gateway(sessions).create_checkout(self.request(OneTimeTerms(500, "usd")))


if __name__ == "__main__":
    unittest.main()
