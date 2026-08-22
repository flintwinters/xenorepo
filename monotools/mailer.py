"""Provider-neutral email delivery and a standard-library SMTP adapter."""

from dataclasses import dataclass
from email.message import EmailMessage
import smtplib
import ssl
from typing import Protocol


@dataclass(frozen=True)
class Mail:
    sender: str
    recipient: str
    subject: str
    text: str


@dataclass(frozen=True)
class DeliveryReceipt:
    provider: str
    external_id: str | None = None


class Mailer(Protocol):
    name: str

    def send(self, mail: Mail) -> DeliveryReceipt: ...


class SmtpMailer:
    """Deliver mail through SMTP without coupling callers to transport details."""

    name = "smtp"

    def __init__(self, host: str, port: int, *, username: str | None = None,
        password: str | None = None, starttls: bool = True, timeout: float = 10) -> None:
        self.host, self.port = host, port
        self.username, self.password = username, password
        self.starttls, self.timeout = starttls, timeout

    def send(self, mail: Mail) -> DeliveryReceipt:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = (
            mail.sender, mail.recipient, mail.subject
        )
        message.set_content(mail.text)
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as connection:
            if self.starttls:
                connection.starttls(context=ssl.create_default_context())
            if self.username:
                connection.login(self.username, self.password or "")
            refused = connection.send_message(message)
        if refused:
            raise RuntimeError(f"SMTP refused {', '.join(sorted(refused))}")
        return DeliveryReceipt(self.name, message.get("Message-ID"))
