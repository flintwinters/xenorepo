# Project direction

## Motivation

Make a realtime match immediately legible, durable, and satisfying to play.

## Architecture

The app owns matchmaking, rounds, player identity, and arena presentation; it
uses generic persistence, realtime, build, and browser-proof contracts.

## Current tasks

- Preserve the typed Preact state/view/transport split and runtime validation of
  the app-owned realtime protocol.
- Preserve browser evidence and stable spatial and color ownership at wide and
  narrow viewports.
- Adopt stable identity and timestamp schemas locally, contributing only
  independently proven infrastructure contracts to shared persistence code.
