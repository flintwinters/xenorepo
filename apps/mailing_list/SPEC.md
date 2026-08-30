# Dispatch Ledger walking-skeleton specification

## Outcome

Dispatch Ledger proves that a reader can enter a paid monthly subscription,
complete a hosted checkout, and observe durable activation. Repeated payment
notifications must not duplicate transitions. Provider and delivery adapters
remain replaceable behind Monotools contracts while commercial policy remains
owned by this monoapp.

## Actors and responsibilities

- A reader supplies an email address, reviews the price, completes checkout,
  and receives an explicit success, cancellation, or failure state.
- The payment provider owns checkout interaction and authenticates its event.
- Dispatch Ledger owns subscriber identity, price policy, payment transitions,
  idempotency, and the user-visible subscription status.
- A mail provider transports app-authored messages only after activation.

## Durable facts and invariants

- Email identity is normalized and unique.
- Every checkout preserves provider identity, amount, currency, state, and
  timestamps; provider checkout and event identifiers are unique per provider.
- Only an authenticated, supported payment event can activate a subscriber.
- Replaying the same event is a successful no-op and cannot duplicate facts.
- Unknown checkouts and malformed or unauthenticated events fail closed without
  changing subscriber state.
- Provider outages leave pending facts recoverable and never claim activation.

## Walking-skeleton lifecycle

1. The app publishes its monthly offering.
2. A reader submits an email and receives a provider-hosted checkout URL.
3. The sandbox provider offers deterministic complete and cancel controls.
4. A signed provider notification changes the checkout state exactly once.
5. The return view resolves the checkout and displays active, cancelled, failed,
   or still-pending status without exposing internal database identifiers.

Stripe Checkout now follows the accepted sandbox lifecycle through a monthly
subscription Checkout Session and signed checkout events. Recurring renewal and
cancellation policy, wallet presentation, unsubscribe, publication authoring,
and email delivery remain later lifecycle expansions.

## Stripe test-mode operation

The app uses its deterministic sandbox unless both
`MAILING_LIST_STRIPE_SECRET_KEY` and `MAILING_LIST_STRIPE_WEBHOOK_SECRET` are
configured. An incomplete pair fails startup. Forward Stripe CLI events to
`/api/webhooks/payments/stripe`; the CLI-issued `whsec_…` value is the webhook
secret. The return view resolves the Checkout Session state from durable local
facts and never treats a browser redirect as proof of payment.

## Acceptance criteria

- Browser acceptance covers enrollment, sandbox payment, return, and visible
  active status through public HTTP routes.
- API tests cover signature rejection, malformed and unknown events, event
  replay, cancellation, and repeated enrollment.
- Restarting against the same database preserves the resulting lifecycle facts.
- Root `uv run manage.py verify` passes with deterministic wide and narrow visual
  baselines.
