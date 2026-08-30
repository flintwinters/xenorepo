"""Safe local providers used until live adapter credentials are configured."""

import hashlib
import hmac
import json

from monotools.integrations.commerce import CheckoutRequest, HostedCheckout, PaymentNotification
from monotools.integrations.mailer import DeliveryReceipt, Mail


class SandboxGateway:
    name = "sandbox"

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode()

    def create_checkout(self, request: CheckoutRequest) -> HostedCheckout:
        return HostedCheckout(self.name, request.reference, f"/sandbox/checkout/{request.reference}")

    def parse_notification(self, payload: bytes, signature: str | None) -> PaymentNotification:
        expected = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        if signature is None or not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid payment signature.")
        try:
            event = json.loads(payload)
            return PaymentNotification(self.name, event["event_id"],
                event["checkout_id"], event["state"])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("Malformed payment notification.") from error

    def notification(self, checkout_id: str, state: str) -> tuple[bytes, str]:
        payload = json.dumps({"event_id": f"sandbox-{checkout_id}-{state}",
            "checkout_id": checkout_id, "state": state}, separators=(",", ":")).encode()
        return payload, hmac.new(self._secret, payload, hashlib.sha256).hexdigest()


class RecordingMailer:
    name = "recording"

    def __init__(self) -> None:
        self.messages: list[Mail] = []

    def send(self, mail: Mail) -> DeliveryReceipt:
        self.messages.append(mail)
        return DeliveryReceipt(self.name, str(len(self.messages)))
