# Project direction

## Motivation

Provide a compact durable publishing workflow with trustworthy account access.

## Architecture

The app owns accounts, authentication, posts, and projections; it consumes only
generic persistence, transport, build, and lifecycle contracts.

## Current tasks

- Adopt stable identity and timestamp schemas within the app-owned persistence
  model and retain authentication policy beside its domain behavior.
- Evaluate an opaque-auth ORM template only after another independent monoapp
  proves the exact infrastructure boundary.
