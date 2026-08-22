# Dispatch Ledger

A FastAPI and Lit proving ground for paid mailing-list subscriptions. Run it
from the repository root with `python manage.py serve mailing_list`.

The current checkpoint uses a sandbox hosted-checkout adapter. Its domain model
and API depend only on `PaymentGateway`; live processors are introduced as
adapters, never as domain dependencies. SMTP delivery uses the shared `Mailer`
contract and `SmtpMailer` adapter.
