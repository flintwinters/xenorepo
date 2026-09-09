# Operator credential setup

## Purpose

Use this policy when a monoapp depends on credentials that only a human operator
can create through an external provider. Provider- and product-specific setup
belongs in that monoapp's documentation, never in Xenorepo documentation.

## Safe handoff

1. The monoapp documents every required setting, accepted format, provider
   prerequisite, and a secret-free acceptance check beside its source.
2. The operator creates credentials with the least privileges needed and starts
   with a provider's test or sandbox environment when one exists.
3. Store secret values only in the monoapp's ignored environment file or the
   runtime's secret-injection mechanism. Never place them in conversations, issues,
   command arguments, logs, screenshots, or versioned files.
4. Confirm ignored local files do not appear in `git status --short`.
5. Record only non-secret configuration and evidence from the monoapp's
   acceptance check.

If setup cannot be completed without a public endpoint, verified identity, or
other external prerequisite, report that exact prerequisite and stop. Do not
weaken authentication or substitute production credentials to bypass it.

## Recovery and rotation

Create a replacement credential, update the secret store, run the owning
monoapp's acceptance check, and only then revoke the old credential. If a
provider exposes a credential only once, loss requires replacement rather than
recovery. A partially configured credential pair or dependency must fail closed
with a contextual diagnostic.
