# Project direction

## Motivation

Make a realtime match immediately legible, durable, and satisfying to play.

## Architecture

The app owns matchmaking, rounds, player identity, and arena presentation; it
uses generic persistence, realtime, build, and browser-proof contracts.

## Current tasks

- Center the reveal in a dominant arena with distinguishable hand silhouettes
  and stable spatial and color ownership at wide and narrow viewports.
- Preserve browser evidence for the accepted hierarchy and realtime workflow.
- Adopt stable identity and timestamp schemas locally, contributing only
  independently proven infrastructure contracts to shared persistence code.
