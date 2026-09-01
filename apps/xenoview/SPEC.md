# Xenorepo Cockpit — Product Specification

## User problem and product intent

The Xenorepo owner needs one trustworthy command-and-control view of the repository's shape and trajectory. Source files, Monotools modules, application declarations, architectural constraints, and verification results exist in different places; reading them individually makes broad change hard to perceive. The cockpit turns those facts into a compact, read-only operational picture without becoming a second build system or a source of architectural policy.

The product succeeds when an owner can answer, within a minute: how large is the repository, where is it growing, which Monotools modules carry the most weight, how monoapps depend on the platform, whether structural guardrails are healthy, and whether the trend is improving. Measurements are evidence, not quality theater: every score exposes its underlying count and avoids combining unrelated facts into an opaque grade.

## Feature inventory

- An overview scorecard with source files, source lines, repository bytes, monoapps, Monotools modules, tests, documentation coverage, architecture violations, oversized files, and complex functions.
- Automatic, bounded Git history showing absolute maintained-text line-count graphs per monoapp and added/deleted lines per commit grouped by monoapp and language; no operator sampling is required. Durable snapshots remain optional broad-metric baselines.
- A Monotools module inventory showing file size, line count, public definitions, exact consuming monoapps, and direct internal dependencies.
- A bounded, interactively collapsible repository tree showing directories and relevant files with byte and line totals, excluding generated, private, and runtime-heavy directories. Every app and maintained end-to-end test subtree remains measurable but starts collapsed.
- Visible measurement time, repository revision, dirty state, exclusions, failures, and definitions so the dashboard cannot imply false precision.
- A local monoapp overview with live health, deterministic URLs, and start/stop controls that reuse Monotools lifecycle rules and stop only Xenoview-owned processes.

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

FastAPI serves a Preact client and three read-only views backed by one deterministic repository scanner:

- `GET /api/overview` returns the current scorecard, audit counts, latest saved delta, exclusions, revision, and dirty state.
- `GET /api/modules` returns the Monotools inventory.
- `GET /api/tree` returns a bounded hierarchical repository projection.
- `GET /api/monoapps` reports local runtime state; same-origin `POST` transitions start and stop a named monoapp.
- `GET /api/repository-history` derives absolute app line trajectories plus commit, app, and language changes from Git without mutation. `GET /api/history` returns optional saved metric baselines; `POST /api/snapshots` records one after same-origin validation.

SQLite stores snapshots in `data/xenoview.db`; `XENOVIEW_DATABASE_URL` may select another SQLAlchemy database. Scans never write to source control or execute repository code. Results use a short process-local cache invalidated by the explicit snapshot operation.

## Real-world pilot and acceptance

Run the cockpit against Xenorepo, inspect the largest files and Monotools modules, trace exact monoapp consumers back to `app.yaml`, and inspect several commits across app and language changes without recording a snapshot. Optionally save two baselines around a small source change and confirm that generated data does not distort either projection.

Automated acceptance covers deterministic exclusions and ordering, line/byte aggregation, module dependency extraction and exact consumers, audit mapping, bounded tree output, revision/dirty reporting, bounded automatic Git history grouped by app and language, snapshot idempotence, restart persistence, same-origin mutation protection, modular TypeScript compilation, self-contained FastAPI delivery, and browser navigation across the overview, explorer, and history views.

## Deferred scope

Live filesystem watching, remote Git providers, submodule-internal history aggregation, CI ingestion, commit authorship, historical source-tree reconstruction, semantic code quality scoring, runtime telemetry, task management, source editing, arbitrary filesystem browsing, and predictive forecasts are deferred. The cockpit owns product presentation and snapshot persistence; generic measurements should move into Monotools only after another consumer proves a stable shared contract.
