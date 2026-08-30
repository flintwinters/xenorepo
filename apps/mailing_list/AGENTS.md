# Project direction

## Motivation

Prove a trustworthy paid-subscription lifecycle from checkout through delivery.

## Architecture

The app owns subscriber, payment, webhook, and delivery policy behind FastAPI;
shared code is limited to provider-neutral infrastructure contracts.

## Current tasks

- Complete the `SPEC.md` sandbox lifecycle through public HTTP boundaries,
  including signed notification handling, idempotent activation, and visible
  checkout status.
- Add live hosted checkout, wallet-assisted payment, and SMTP only after sandbox
  lifecycle acceptance.
- Keep payment, subscription, and delivery policy app-owned; share only
  provider-neutral contracts with an independently proven consumer boundary.
