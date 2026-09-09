# Xenorepo

Xenorepo is a laboratory for building and operating small applications through
one reusable platform. **Monotools** owns discovery, scaffolding, builds,
runtime conventions, and verification; the applications in `apps/` prove and
improve those shared workflows.

Each monoapp uses FastAPI, Preact, and typed metadata while keeping its product
code independent from every other app. Mature monoapps can be promoted to their
own Git repositories without losing their verified dependency on Xenorepo.

## Getting started

Install [uv](https://docs.astral.sh/uv/) and Node.js 22, then use the root
management command:

```console
uv run manage.py list
uv run manage.py status
uv run manage.py test
```

Run `uv run manage.py --help` to discover repository and app-specific commands.
`uv run manage.py verify` is the complete build, test, and browser-validation
checkpoint for a fully provisioned checkout.

After promoting a monoapp to a submodule, create a separately cloned workspace
that retains only that app while preserving this repository as `upstream`:

```console
uv run manage.py monoapp fork-workspace app_name \
  --owner github_owner --repository app-workspace --visibility private
```

The routine verifies the focused clone before creating or pushing its GitHub
repository. Pass `--directory` to override the default sibling directory.

See [AGENTS.md](AGENTS.md) for the project architecture and invariants, and
[LIBRARIES.md](LIBRARIES.md) for shared-library boundaries.
