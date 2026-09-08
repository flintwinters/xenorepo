# Portable deployment membrane

Status: architectural proposal; no deployment commands or adapters exist yet.

## Outcome and boundary

Build a monoapp once as an immutable OCI image and deploy that same release to
ECS on Fargate or a compatible self-hosted target. Compatibility means satisfying
a versioned workload contract and passing its conformance checks, not merely
being able to start a container. Portability does not imply equal availability,
capacity, cost, or automatic migration of live data between providers.

The membrane belongs in Monotools orchestration, between application intent and
target execution. Apps declare what they require; adapters implement deployment
on a target. AWS resource identifiers and host topology never enter app code.

```text
AppDefinition + immutable release + deployment intent + target bindings
                              |
                  validation and deployment plan
                              |
              target adapter: ECS/Fargate or self-hosted
                              |
                 observed state and rollout evidence
```

Reuse `AppDefinition`, lifecycle builds and evidence, environment resolution,
FastAPI construction, and SQLAlchemy configuration. Extend their authoritative
contracts instead of creating a second app inventory or configuration loader.
Generic deployment belongs under `monotools/orchestration/`; repository-specific
target composition belongs under `monotools/provisioning/`, following
`LIBRARIES.md`. Runtime app imports must not pull in deployment SDKs.

## Four separate contracts

| Contract | Owns | Does not own |
| --- | --- | --- |
| Workload requirements | HTTP port, probes, shutdown behavior, configuration schema, logical dependencies, writable scratch, concurrency constraints | Cloud resource names, desired production capacity |
| Release | Image digest, OS/architecture, app and Monotools revisions, contract version, build evidence, migration entrypoint and schema compatibility | Secrets, environment-specific endpoints |
| Deployment intent | Release selection, replicas, resource budget, domain, rollout policy | Scheduler implementation |
| Target bindings and capabilities | Dependency endpoints, secret references, ingress, identity, capacity and supported guarantees | Application domain behavior |

The existing app YAML remains authoritative for application requirements; a
release captures the validated requirements for that build. Target configuration
binds logical dependencies to concrete resources. Validate requested guarantees
against target capabilities before mutation. Reject unsupported combinations or
show explicit resource rounding in the plan; never silently weaken semantics.

## Small initial runtime profile

- One Linux OCI image containing FastAPI, compiled frontend artifacts, app
  metadata, and its pinned Monotools dependency. Preserve the package layout
  required by existing local entrypoints without shipping unrelated apps.
- One HTTP listener; ingress provides TLS, correct host/scheme forwarding and
  WebSocket support when required. Trust forwarded headers only from configured
  proxies; public origin configuration must preserve existing origin checks.
- Configuration is validated at startup. Bind logical secrets through the
  existing environment keys initially; do not bake dotenv files into images or
  include resolved secret values in plans, logs, or deployment evidence.
- Non-root execution, read-only application files, declared ephemeral scratch,
  stdout/stderr logs, bounded startup and graceful SIGTERM shutdown.
- Separate liveness from readiness. Readiness checks required dependencies and
  compatible schema with bounded probes; dependency failure should withdraw
  traffic without causing an endless liveness restart loop.
- Durable facts live outside the container. PostgreSQL is the proposed baseline
  for portable durable deployment. SQLite remains a local development option;
  a future persistent-volume profile must state its single-writer, placement,
  backup and recovery constraints explicitly.
- Start with one process and one replica unless the app proves otherwise.
  Process-local realtime registries require an explicit replacement policy;
  even a one-replica rolling update can temporarily create two active processes.
  Such apps initially require stop/start replacement with declared downtime.
  Multi-replica delivery needs a separately proven shared transport contract.

Database, blob storage, mail and other integrations are dependency contracts,
not methods on a giant hosting interface. Add bindings only for demonstrated
requirements. Hosting portability and dependency portability are separate:
moving compute while retaining an AWS-only dependency does not prove complete
self-hostability. Do not invent generic storage or queue APIs in advance.

## Adapter and lifecycle responsibilities

Use a small conceptual adapter surface: inspect capabilities and observed state,
plan, apply an identified operation, observe it, and retrieve diagnostics.
Rollback selects a previous compatible release through the same plan/apply path.
Retirement is an explicit planned operation with durable resources retained by
default. These are proposed responsibilities, not settled Python signatures.

Monotools owns release identity, compatibility rules, deployment intent,
operation records, normalized status, deadlines, and acceptance evidence.
The target owns process supervision and its native rollout mechanisms; Monotools
must not build a competing scheduler. Provision shared networks, hosts, databases
and ingress separately, then bind them into application deployments. Adapters
may manage clearly owned service resources without owning the entire account.

An operation records target/app identity, desired generation, release digest,
plan fingerprint, resource ownership and observed provider identifiers in a
durable operator store. Serialize conflicting operations per app/target. Refuse
stale plans and reconcile after interruptions; an API timeout means unknown
outcome until observation resolves it. Retries must not duplicate resources.
Report partial progress, last-known state, uncertainty and recovery commands.

A rollout progresses through validation, dependency checks, a serialized
migration job when required, candidate startup, readiness, traffic activation,
and a bounded stabilization period. Unsupported safe overlap requires an
explicit downtime plan. Deployment success requires evidence from the actual
ingress path, not merely a successful scheduler request.

App-owned migrations run from the release image with database-level exclusion
and a version ledger. Reuse migration primitives where their semantics fit;
current startup `create_all` and prepare callbacks are not proof of production
migration safety. Old and new schema compatibility must permit the selected
rollout and rollback. Destructive migrations need a separate recovery plan;
switching an image never promises to undo data changes.

## First proof and acceptance

Implement two adapters alongside the contract: ECS/Fargate and a single Linux
host with an OCI engine, native supervision and a TLS reverse proxy. Choose the
host engine after inspecting the intended host. Do not require Kubernetes;
additional schedulers should only need adapters. Prefer established native
declarative mechanisms where they satisfy the operation/recovery contract.

Prove the same image on both targets with two independent apps: a durable CRUD
app and a realtime app. Initially bind existing PostgreSQL resources. Exercise
fresh deploy, repeated apply, missing configuration, incompatible capabilities,
dependency outage, failed readiness, interrupted apply, process/host restart,
schema failure, compatible rollback, and retirement without data deletion.
Verify durable records, actual public routing, secret redaction, connection
recovery and any declared downtime. Separately rehearse database backup/restore
and provider transfer before claiming complete operational portability.

Routinize Python-driven conformance and integration checks through root
`manage.py` with Rich/Typer, using visible ignored per-app `data/` artifacts.
Live target checks require configured infrastructure and must report untested
targets explicitly. Integrate offline contract checks into `verify`; run the
full verification checkpoint for implementation changes. Existing central
tests remain generic and app-owned tests supply product acceptance behavior.
Catalog the shared contract in `LIBRARIES.md` when it is implemented and adopted.

## Evidence, assumptions and alternatives

Repository evidence: `AppDefinition` already owns metadata;
`runtime/application.py` serves built artifacts but `/health` is unconditional;
`persistence/database.py` performs schema creation during factory construction;
`runtime/realtime.py` holds connections in memory. No Fargate adapter was found
in Monotools. These establish reuse opportunities and readiness/concurrency gaps.

AWS documents Fargate-specific task constraints and ECS service supervision in
[task definition differences](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-tasks-services.html)
and [ECS services](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html).
Those mechanisms belong behind the adapter, not in portable workload metadata.

Inaction leaves deployment conventions unproved. A Fargate-shaped wrapper would
export AWS assumptions; a universal infrastructure language would add speculative
surface area. The smallest adequate intervention is the limited runtime profile,
explicit capabilities and two concrete implementations.

Weakest assumption: a single HTTP service with external durable dependencies
covers the first production workloads. Background work, large local files, or
distributed realtime requirements may require additional profiles.

Reversal test: switch only deployment intent and target bindings, deploy the
same release digest, and pass the same applicable acceptance checks. If app code
or build output must change for the provider, the membrane is leaking. A data
transfer remains a separately planned operation, not a side effect of switching
the target.
