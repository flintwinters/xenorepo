# Project direction

## Motivation

Offer a concise, non-diagnostic working-style inventory with clear results.

## Architecture

The app owns its inventory, scoring, copy, and self-contained browser artifact;
Monotools supplies only generic build and lifecycle behavior.

## Current tasks

- Own all inventory copy, scoring, interaction, and presentation assertions in
  this app's suite; remove those expectations from central platform tests.
- Preserve current routes, built artifact, and user-visible workflow while
  obsolete platform compatibility APIs are removed.
