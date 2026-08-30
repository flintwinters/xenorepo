# Project direction

## Motivation

Prove a trustworthy paid-subscription lifecycle from checkout through delivery.

## Architecture

The app owns subscriber, payment, webhook, and delivery policy behind FastAPI;
shared code is limited to provider-neutral infrastructure contracts.

## Current tasks

- Preserve the verified sandbox enrollment lifecycle, actionable checkout
  failures, and deterministic wide/narrow membership-desk baselines.
- Prove the configured Stripe adapter with a test-mode subscription and signed
  CLI-forwarded webhook before enabling live keys.
- Add wallet-assisted payment and SES delivery only after Stripe test-mode
  acceptance.
- Keep payment, subscription, and delivery policy app-owned; share only
  provider-neutral contracts with an independently proven consumer boundary.
