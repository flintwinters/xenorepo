# Project direction

## Motivation

Prove a trustworthy paid-subscription lifecycle from checkout through delivery.

## Architecture

The app owns subscriber, payment, webhook, and delivery policy behind FastAPI;
shared code is limited to provider-neutral infrastructure contracts.

## Current tasks

- Preserve the verified sandbox enrollment lifecycle, actionable checkout
  failures, and deterministic wide/narrow membership-desk baselines.
- Add live hosted checkout, wallet-assisted payment, and SMTP only after sandbox
  lifecycle acceptance.
- Keep payment, subscription, and delivery policy app-owned; share only
  provider-neutral contracts with an independently proven consumer boundary.
