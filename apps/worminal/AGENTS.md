# Project direction

## Motivation

Make local terminal access dependable while keeping its security boundary clear.

## Architecture

The app owns PTY, shell, terminal-emulation, and window policy behind its
FastAPI service; Monotools receives only generic lifecycle parameters.

## Current tasks

- Own composition, command options, environment handling, and browser behavior
  that currently survives in legacy central CLI compatibility coverage.
- Validate loopback-only PTY bridging, terminal emulation, child-process cleanup,
  and browser-window management with app-owned repeatable tests.
- Express special runtime policy through generic lifecycle parameters without
  placing terminal or process policy in Monotools.
