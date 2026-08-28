# Project direction

## Motivation

Provide a small, durable realtime room whose history remains trustworthy.

## Architecture

The app owns participants, rooms, messages, and connection persistence behind
its FastAPI service and declares generic lifecycle needs to Monotools.

## Current tasks

- Own persistence, migration, realtime, and product assertions in this app's
  suite; characterize those contracts before central tests are generalized.
- Adopt stable identity and timestamp schemas locally, then provide evidence
  for any generic realtime connection template without exporting domain facts.
