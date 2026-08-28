# Project direction

## Motivation

Prove a trustworthy paid-subscription lifecycle from checkout through delivery.

## Architecture

The app owns subscriber, payment, webhook, and delivery policy behind FastAPI;
shared code is limited to provider-neutral infrastructure contracts.

## Current tasks

- Extend the proven subscription contracts with hosted checkout, including
  wallet-assisted payment, signed webhooks, and SMTP only after sandbox
  lifecycle acceptance.
- Keep payment, subscription, and delivery policy app-owned; share only
  provider-neutral contracts with an independently proven consumer boundary.
