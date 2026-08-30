# Fargate Deployment Plan

## Outcome

Give every managed monoapp at most one active AWS Fargate deployment. A single
Xenorepo command verifies and builds the selected app, packages the same FastAPI
runtime as an immutable `.monoapp` OCI image, publishes that image to Amazon
Elastic Container Registry (ECR), and exposes it at a stable app-specific HTTPS
hostname.

```text
uv run manage.py fargate deploy APP
uv run manage.py fargate destroy APP
```

The V1 success condition is `https://APP.<configured-domain>/health` returning a
healthy response from the exact image selected by `deploy`. Deployment is not an
update mechanism: a different revision cannot replace an active app until the
operator explicitly destroys that app's deployment.

## Design review

### Actors and responsibilities

- The local operator selects an app and initiates deployment or destruction
  through root `manage.py`, the repository's sole routine entrypoint.
- The monoapp declares its existing typed application metadata and implements
  its product behavior. It contains no AWS policy.
- Monotools orchestration validates the app, compiles its frontend, and resolves
  the same FastAPI application used by `manage.py APP serve`.
- Xenorepo provisioning owns image assembly, AWS configuration, shared resource
  discovery, app-scoped resources, reconciliation, readiness, and recovery
  diagnostics. Reusable orchestration must not depend on this policy.
- AWS supplies the registry, networking, load balancing, DNS, certificates,
  logs, and one bounded Fargate task per deployed app.

### Invariants

- An app has zero or one active deployment.
- An active deployment identifies one immutable image digest, never only a
  mutable tag.
- Local serve and Fargate start the same FastAPI application contract.
- The container listens on `0.0.0.0:8000`, exposes `/health`, runs as non-root,
  and writes mutable state only below `/data`.
- Public traffic terminates TLS at the Application Load Balancer (ALB); the
  container is not publicly addressable.
- Shared infrastructure is reconciled but never removed by `destroy APP`.
- App-scoped resources carry app identity and ownership tags, and teardown
  selects by verified identity rather than by broad name pattern.
- Success means the public HTTPS health endpoint serves the requested image,
  not merely that AWS accepted resource creation.
- Failure preserves unrelated deployments and reports the last stable state and
  an exact recovery command.

### Alternatives

Doing nothing preserves local-only operation but does not establish a production
artifact or public deployment contract. A separate deployment service or
app-owned Dockerfiles would duplicate lifecycle knowledge and allow apps to
drift from Monotools. Updating an active service in place would reduce operator
steps, but introduces rollback, draining, migration, and mixed-revision states
before those controls exist.

The simplest adequate intervention is therefore a root `fargate` command group
implemented by Xenorepo provisioning. It composes the existing validation,
frontend build, and runtime contracts, while an immutable destroy-before-replace
rule bounds V1 state transitions and makes operator intent explicit.

### Evidence and decision boundary

The current repository already centralizes app discovery and lifecycle in root
`manage.py`; Monotools already builds each compiled frontend and reserves
`/health`; and `LIBRARIES.md` assigns repository-specific composition to
`monotools/provisioning/`. Those contracts support a thin provisioning layer
instead of a parallel app lifecycle.

The weakest assumption is that ephemeral SQLite is useful for every V1 workload.
Evidence of required cross-task durability, zero-data-loss expectations, or
stateful revision replacement would reverse that choice and require a designed
persistence and migration contract before deployment updates are admitted.

## Artifact contract

The build produces a Linux AMD64 OCI image referred to as a `.monoapp` image.
The image contains one self-sufficient executable and everything required to
start it:

- application backend code and identity metadata;
- Monotools runtime code;
- locked Python and native dependencies;
- the compiled, self-contained frontend `dist/` artifact;
- database migrations;
- a TLS trust store for outbound HTTPS; and
- source revision and build metadata.

The executable starts the same FastAPI application resolved by local serve,
binds `0.0.0.0:8000`, and handles termination signals with bounded graceful
shutdown. It runs under a fixed non-root UID/GID and has no writable application
or dependency directories. `/data` is its only mutable filesystem contract and
contains the ephemeral SQLite database and other explicitly app-owned runtime
state.

The image excludes secrets, deployment configuration, logs, user data, local
development data, caches, source-control metadata, and AWS credentials. Its
entrypoint accepts no host, port, or watch overrides. Image metadata records at
least the monoapp name, source revision, Monotools revision, and deterministic
artifact version. ECR transports the completed image unchanged; no remote build
step modifies it.

An image digest is the deployment identity. Human-readable tags may include the
app and revision for inspection, but reconciliation and task definitions pin the
digest.

## Runtime and repository configuration

Fargate configuration is Xenorepo deployment policy, not per-command input. A
typed repository configuration defines:

- AWS account and region;
- base domain and Route 53 hosted-zone identity;
- ACM certificate identity or its deterministic discovery rule;
- VPC, public ALB subnets, and private task subnets;
- task CPU and memory;
- log retention and health-check thresholds; and
- bounded readiness and AWS-operation timeouts.

Configuration is validated in full before local build or AWS mutation. Unknown
apps, malformed domains, unsupported CPU/memory pairs, missing credentials,
ambiguous AWS resources, and unavailable prerequisites fail contextually.
Secrets remain in an external AWS secret provider and enter tasks only through
explicit app metadata added in a future secret contract; V1 does not infer or
upload values from the local environment.

The runtime has fixed controls:

| Concern | Contract |
| --- | --- |
| Container host | `0.0.0.0` |
| Container port | `8000` |
| ALB listeners | `80` redirects to `443`; `443` terminates TLS |
| Health path | `/health` |
| Mutable path | `/data` only |
| Watch mode | Unsupported |
| Desired task count | Exactly one |
| CPU architecture | Linux AMD64 |

## AWS resource model

Shared resources are created or adopted only after their identity, ownership,
and configuration match the repository contract:

- one ECR repository for `.monoapp` images;
- one VPC networking boundary, or explicitly configured existing networking;
- one ECS cluster;
- one internet-facing ALB with HTTP and HTTPS listeners;
- one Route 53 hosted zone and one ACM certificate covering app hostnames;
- task execution and runtime IAM roles with distinct least-privilege policies;
  and
- shared security groups and log-group policy.

Each active app owns only:

- one digest-pinned ECS task definition revision;
- one ECS service with desired count one and bounded deployment settings;
- one target group on port `8000` with `/health` checks;
- one HTTPS listener rule matching exactly its hostname;
- one Route 53 alias record for that hostname;
- one app log stream namespace; and
- ephemeral task storage containing `/data`.

Every managed resource is tagged with the repository deployment identity,
environment, scope (`shared` or `app`), app name where applicable, and image
digest where applicable. Listener-rule priorities and AWS names are derived by
a deterministic collision-aware allocator rather than by app ordering.

The task runs in private subnets without a public IP. Its security group accepts
port `8000` only from the ALB security group. Egress supports ECR image pull,
logging, AWS APIs required by the execution role, DNS, and outbound TLS needed
by monoapps. The ALB accepts public `80` and `443`; HTTP always redirects to
HTTPS. WebSocket upgrades pass through without a separate service.

## State machine

The deployment state is derived from AWS facts and the requested local digest:

| Observed state | `deploy APP` | `destroy APP` |
| --- | --- | --- |
| Absent | Build, publish, provision, and verify | Report already absent |
| Creating same digest | Reconcile and wait within bounds | Remove app resources |
| Healthy same digest | Report the existing healthy URL | Remove app resources |
| Unhealthy same digest | Reconcile safe omissions, diagnose, and fail if still unhealthy | Remove app resources |
| Active different digest | Refuse replacement; instruct `destroy APP` | Remove app resources |
| Partial app resources | Reconcile only if identity and digest are consistent; otherwise fail safely | Remove verified app resources |
| Ambiguous or foreign resources | Refuse mutation and identify the conflict | Refuse mutation and identify the conflict |

There is no mutable local deployment-state file. AWS tags, task definitions,
service state, listener rules, DNS, and image digests are authoritative. This
allows recovery after an interrupted local command without trusting stale local
state.

## `deploy APP` lifecycle

`uv run manage.py fargate deploy APP` performs these phases in order:

1. Discover the managed app and validate repository deployment configuration,
   local toolchain availability, credentials, region, and AWS identity without
   mutation.
2. Reuse the existing app validation and frontend-build lifecycle. A validation
   or build failure performs no AWS mutation.
3. Compile the self-sufficient AMD64 executable, assemble the minimal image,
   inspect its entrypoint, user, platform, labels, filesystem policy, and
   `/health` behavior locally, then resolve its immutable digest.
4. Inspect app-scoped AWS facts. Refuse immediately if an active deployment has
   a different digest.
5. If that digest is already publicly healthy for the app, report the existing
   URL and make no changes.
6. Idempotently reconcile missing shared infrastructure. Existing resources
   must match ownership and security invariants before adoption.
7. Push the already-validated bytes to ECR and verify the registry digest equals
   the local digest.
8. Reconcile the app target group, digest-pinned task definition, ECS service,
   listener rule, and DNS alias. Never alter another app's route or service.
9. Wait within explicit time bounds for one running healthy task, healthy ALB
   target registration, DNS resolution, valid TLS, and a successful public
   `https://APP.<configured-domain>/health` response.
10. Report the URL, image digest, revision, and resource identities only after
    public readiness passes.

If a phase is interrupted, rerunning the same command reconciles the same digest.
If readiness fails, the command preserves diagnostic resources, reports the
failed layer and observed AWS state, and offers `fargate destroy APP` as the
canonical cleanup path. It does not report a successful deployment merely
because the task is running.

## `destroy APP` lifecycle

`uv run manage.py fargate destroy APP` discovers and validates the named app's
owned resources before mutation. If none exist, it reports the deployment as
already absent and exits successfully.

For an active or partial deployment it:

1. removes the app's DNS alias and listener rule so no new public traffic is
   routed to the task;
2. scales the app service to zero and waits for bounded connection draining;
3. deletes the ECS service and target group;
4. deregisters app-owned task definition revisions when safe; and
5. reports that ephemeral `/data` was destroyed with the task.

Destroy does not delete ECR images, log history, IAM roles, networking, the ALB,
listeners, hosted zone, certificate, cluster, or any other app's resources.
Repeated or interrupted destroys converge on absence. A resource with missing,
ambiguous, or foreign ownership is reported rather than guessed at or deleted.

## Failure and recovery behavior

- Missing local tools or an unsupported container platform fail before AWS
  mutation and name the canonical bootstrap or configuration repair.
- Expired credentials and AWS unavailability retain the last confirmed state;
  retries are bounded and safe operations are idempotent.
- An image push interruption is recoverable by digest; an incomplete tag is not
  treated as deployed.
- ECS placement, image pull, startup, health, DNS, certificate, and public-route
  failures are distinguished in diagnostics.
- A crashed task may be replaced by ECS only with the same task definition and
  image digest; this is recovery, not a revision update.
- Malformed or conflicting existing infrastructure blocks mutation rather than
  broadening permissions or silently replacing resources.
- Local interruption never triggers automatic teardown. The operator can rerun
  the same deploy to reconcile or destroy the named app explicitly.

## Implementation checkpoints

Each checkpoint ends with `uv run manage.py verify` and its own detailed commit.

1. **Contracts and configuration.** Add typed deployment configuration, app and
   shared resource identities, digest-based state inspection, contextual errors,
   and root `fargate` command discovery without mutation.
2. **Artifact builder.** Add deterministic executable and image assembly by
   composing existing validation/build/runtime functions. Prove platform, user,
   fixed networking, read-only filesystem behavior, `/data`, metadata, static
   frontend, migrations, outbound TLS, `/health`, and graceful shutdown.
3. **AWS shared provisioning.** Add narrow AWS adapters and idempotent shared
   resource reconciliation with ownership, IAM, network, certificate, logging,
   and collision tests. Keep SDK details behind typed provisioning interfaces.
4. **App deployment reconciliation.** Add ECR digest publication, target group,
   task definition, service, route, DNS, immutable-revision refusal, interrupted
   retry behavior, and public readiness proof.
5. **Scoped destruction.** Add dependency-ordered teardown, already-absent
   success, partial-state recovery, foreign-resource refusal, and proofs that
   shared and other-app resources remain unchanged.
6. **Real-world validation.** Deploy representative static, SQLite, outbound-TLS,
   and WebSocket monoapps; verify two simultaneous app hostnames, same-digest
   idempotence, different-digest rejection, public TLS health, task recovery,
   and app-scoped destruction. Record reproducible evidence through root
   `manage.py` routines.

Tests use project-owned visible ignored `data/` locations and deterministic fake
AWS boundaries for routine coverage. Live AWS validation is an explicit root
`manage.py` command with named configuration, bounded cost, retained evidence,
and app-scoped cleanup; it is never an ad-hoc script.

## Acceptance criteria

- Local serve and the `.monoapp` executable demonstrably resolve the same
  FastAPI application and reserve the same `/health` contract.
- One deploy command produces a healthy
  `https://APP.<configured-domain>` endpoint from an immutable ECR digest.
- Repeating deploy with the same digest returns the existing healthy URL without
  replacing the task definition or service.
- Deploying another revision while the app is active fails before replacement
  and names the required destroy command.
- Representative static, ephemeral-SQLite, outbound-TLS, and WebSocket monoapps
  pass public end-to-end checks.
- Destroying one of two deployed apps removes only the named app's route, task,
  target group, and ephemeral data; the other app and shared infrastructure stay
  healthy.
- Destroy is successful when the deployment is already absent and converges
  after interruption.
- Logs, secrets, user data, and deployment configuration are absent from the
  image; the task is non-root and writable only under `/data`.
- Every recurring build, validation, deployment proof, and cleanup operation is
  exposed through root `manage.py`.
- `uv run manage.py verify` passes at every completed implementation checkpoint.

## Deferred work

V1 deliberately excludes in-place updates, blue/green or canary deployment,
rollback, durable databases or files, backups, S3 artifacts, CodeBuild, public
submission workflows, signing and attestations, multi-operator locking,
automatic expiry, autoscaling, multiple environments, and hosted deployment
APIs. Each requires its own state, authorization, recovery, and acceptance
contract rather than an implicit extension of this walking skeleton.
