# Xenorepo Cockpit — Product Specification

## User problem and product intent

The Xenorepo owner needs one trustworthy command-and-control view of the repository's shape and trajectory. Source files, Monotools modules, application declarations, architectural constraints, and verification results exist in different places; reading them individually makes broad change hard to perceive. The cockpit turns those facts into a compact, read-only operational picture without becoming a second build system or a source of architectural policy.

The product succeeds when an owner can answer, within a minute: how large is the repository, where is it growing, which Monotools modules carry the most weight, how monoapps depend on the platform, whether structural guardrails are healthy, and whether the trend is improving. Measurements are evidence, not quality theater: every score exposes its underlying count and avoids combining unrelated facts into an opaque grade.

## Feature inventory

- An overview scorecard with source files, source lines, repository bytes, monoapps, Monotools modules, tests, documentation coverage, architecture violations, oversized files, and complex functions.
- A durable snapshot timeline for comparing broad-strokes metrics over time. Snapshot creation is an explicit operator action and duplicate repository states are idempotent.
- A Monotools module inventory showing file size, line count, public definitions, inbound monoapp declarations, and direct internal dependencies.
- A bounded, interactively collapsible repository tree showing directories and relevant files with byte and line totals, excluding generated, private, and runtime-heavy directories. Maintained end-to-end test subtrees remain measurable but start collapsed.
- A high-level architecture map derived from app declarations and shared import relationships: repository, monoapps, Monotools, and persistence/runtime boundaries.
- Visible measurement time, repository revision, dirty state, exclusions, failures, and definitions so the dashboard cannot imply false precision.

## Scorecard definitions

The primary scorecard tracks independently meaningful quantities rather than a composite score:

- **Source files / lines / bytes:** maintained source and project documentation after deterministic exclusions.
- **Monoapps / Monotools modules:** discovered app definitions and recursively discovered Python modules in semantic packages.
- **Test files / test cases:** routinized Python and browser suites and statically declared test functions.
- **Specification coverage:** active monoapps with `SPEC.md`, reported as numerator and denominator.
- **Architecture violations / large files / complex functions:** the same structural audit concepts enforced by the root workflow.
- **Largest file / median source file:** concentration signals that retain understandable units.
- **Shared-import edges:** declared monoapp-to-platform dependencies, a coarse coupling indicator rather than a quality score.

History retains the stable scalar subset of these measurements, plus revision and timestamp. Deltas compare the current scan with the newest saved snapshot. Changing metric definitions requires a schema version so unlike measurements are never presented as one continuous series.

## Walking skeleton

FastAPI serves a Preact client and four read-only views backed by one deterministic repository scanner:

- `GET /api/overview` returns the current scorecard, audit counts, latest saved delta, exclusions, revision, and dirty state.
- `GET /api/modules` returns the Monotools inventory.
- `GET /api/tree` returns a bounded hierarchical repository projection.
- `GET /api/architecture` returns typed nodes and edges derived from repository structure and app metadata.
- `GET /api/history` returns saved snapshots; `POST /api/snapshots` explicitly records the current stable metrics after same-origin validation.

SQLite stores snapshots in `data/xenoview.db`; `XENOVIEW_DATABASE_URL` may select another SQLAlchemy database. Scans never write to source control or execute repository code. Results use a short process-local cache invalidated by the explicit snapshot operation.

## Real-world pilot and acceptance

Run the cockpit against Xenorepo, inspect the largest files and Monotools modules, trace several monoapp dependency edges back to `app.yaml`, save a snapshot, make a small source change, and save another. Confirm that the timeline and deltas preserve both states across a service restart and that generated data does not distort counts.

Automated acceptance covers deterministic exclusions and ordering, line/byte aggregation, module dependency extraction, app-declaration edges, audit mapping, bounded tree output, revision/dirty reporting, snapshot idempotence, schema-versioned history, restart persistence, same-origin mutation protection, modular TypeScript compilation, self-contained FastAPI delivery, and browser navigation across the overview, modules, explorer, architecture, and history views.

## Deferred scope

Live filesystem watching, background sampling, remote Git providers, CI ingestion, commit authorship, semantic code quality scoring, runtime telemetry, task management, source editing, arbitrary filesystem browsing, and predictive forecasts are deferred. The cockpit owns product presentation and snapshot persistence; generic measurements should move into Monotools only after another consumer proves a stable shared contract.
