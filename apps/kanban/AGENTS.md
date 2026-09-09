# Project direction

## Motivation

Give one person a calm, durable, recoverable board for turning unordered work into visible progress.

## Architecture

Kanban owns its product behavior and consumes generic Monotools contracts from the enclosing
Xenorepo. Keep frontend, backend, tests, and durable domain facts app-owned.

Inventory shared UI primitives and tokens before writing presentation code. Reuse toolkit commands
and empty states unless their semantics are demonstrably unsuitable. Treat every border, gap,
background, shadow, label, and persistent control as a visual cost that needs a functional reason;
containers are visually silent by default. Avoid slogans, serial numbers, eyebrow labels, fake
status, box-within-box composition, and other decorative AI conventions.

## Current tasks

- Keep the shipped single-board walking skeleton and its recoverable archive semantics aligned with
  `SPEC.md`.
- Preserve the deterministic populated wide/narrow baselines and the horizontal workflow structure
  on small screens.
- Keep copy and atomic append/replace import aligned as one explicit, flat current-state contract.
- Keep card logs append-only and distinct from the system activity stream. Migrate every legacy
  card description exactly once to an epoch-dated log entry and every legacy comment once at its
  original timestamp; logs are the sole user-authored card narrative. Retain legacy descriptions
  as hidden recovery evidence until a formal migration lifecycle can remove their columns safely.
- Render the latest log on each board card and the complete ordered log in card details.
- Keep workflow state singular: columns communicate where work stands, with no parallel card
  priority field.
- Keep cards focused on work rather than ownership; there is no assignee field.
- Keep card presentation subordinate to workflow: cards inherit their owning column's theme and
  have no independent color setting.
- Treat board membership and ordinary classification as one tag concept with two subtypes. A card
  belongs to exactly one board tag, while ordinary tags are reusable and many-valued. The Boards
  and Tags views are projections over the same model, never separate copies of work. Keep item
  content out of the Tags view; it is a catalog and metadata view only.
- Keep the ordinary-tag catalog durable even when a tag has no assigned cards. Card details expose
  only ordinary tags for assignment; board membership is never edited as an ordinary tag.
