# Project direction

## Motivation

Keep everyday arithmetic fast, deterministic, and understandable.

## Architecture

The app owns calculation semantics and its browser artifact; it declares only
generic build and runtime needs to Monotools.

## Current tasks

- Own every calculator product assertion in this app's suite; move remaining
  copy, interaction, and compatibility assertions out of root platform tests.
- Preserve current routes, artifact behavior, and user-visible calculation
  semantics while central compatibility surfaces are removed.
