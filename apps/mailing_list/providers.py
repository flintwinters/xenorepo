"""Safe local providers used until live adapter credentials are configured."""

from monotools.commerce import CheckoutRequest, HostedCheckout, PaymentNotification
from monotools.mailer import DeliveryReceipt, Mail


class SandboxGateway:
    name = "sandbox"

    def create_checkout(self, request: CheckoutRequest) -> HostedCheckout:
        return HostedCheckout(self.name, request.reference, f"/sandbox/checkout/{request.reference}")

    def parse_notification(self, payload: bytes, signature: str | None) -> PaymentNotification:
        raise NotImplementedError("Sandbox notifications are injected by tests only")


class RecordingMailer:
    name = "recording"

    def __init__(self) -> None:
        self.messages: list[Mail] = []

    def send(self, mail: Mail) -> DeliveryReceipt:
        self.messages.append(mail)
        return DeliveryReceipt(self.name, str(len(self.messages)))
