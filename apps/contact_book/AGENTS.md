# Project direction

## Motivation

Contact Book is a deliberately simple proving ground for a reusable table view. Keep product data
operations explicit and app-owned so MonoUI can provide excellent presentation without becoming a
hidden state-management framework.

## Architecture

Contact Book owns durable contacts, deterministic sample generation, CRUD, search, sorting, and
pagination. It owns mutation forms composed from MonoUI controls and uses MonoUI `Table` for supplied
columns and rows. FastAPI is the sole service and SQLite is the local durable default.

Inventory shared UI primitives and tokens before writing presentation code. Reuse toolkit commands
and empty states unless their semantics are demonstrably unsuitable. Treat every border, gap,
background, shadow, label, and persistent control as a visual cost that needs a functional reason;
containers are visually silent by default. Avoid slogans, serial numbers, eyebrow labels, fake
status, box-within-box composition, and other decorative AI conventions.

## Current tasks

- Keep the table contract free of fetching, transformation, interaction, and application policy.
- Preserve deterministic generated data and full public-boundary CRUD coverage.
- Inspect populated wide and narrow evidence before changing shared table presentation.
