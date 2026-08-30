# Dispatch Ledger

A FastAPI and Preact proving ground for paid mailing-list subscriptions. Run it
from the repository root with `python manage.py mailing_list serve`. Its Python
suite is app-owned; `python manage.py mailing_list ui-check` runs the universal
wide/narrow browser contract.

The current checkpoint uses a sandbox hosted-checkout adapter. Its domain model
and API depend only on `PaymentGateway`; live processors are introduced as
adapters, never as domain dependencies. SMTP delivery uses the shared `Mailer`
contract and `SmtpMailer` adapter.
