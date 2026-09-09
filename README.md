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
`uv run manage.py verify` is the fast inner-loop build and Python-test checkpoint.
`uv run manage.py release` is the slower mainline gate: it adds fail-closed dependency
security auditing plus framework and app-owned browser validation. AI aesthetic review
remains an explicit nondeterministic `aesthetic-check` rather than a release invariant.
Pull requests and pushes to `main` run the same `release` command in CI.

`uv run manage.py restore` restores locked dependencies and can preserve existing
submodule state. `bootstrap` restores the complete development checkout.

Promote a mature monoapp from the shared monoapp controls, then work directly in
its app directory:

```console
uv run manage.py monoapp promote app_name
cd apps/app_name
```

Promotion creates a Git repository in `data/repositories/<app>` with no hosted remote, then mounts
it as the monoapp submodule. Configure and push an external remote manually when ready.
The mounted `apps/<app>` directory is that repository's working tree; no duplicate
workspace is created. The compatibility command `monoapp fork-workspace <app>` offers
to remove all other clean monoapps from the current Xenorepo, offers promotion when
needed, and reports the same in-place working tree. It refuses to remove an app with
uncommitted work. It renames the source Xenorepo's `origin` remote to `upstream` and
assigns it a disabled push URL, retaining fetch access without risking an accidental
push. The eventual hosted fork can be configured separately as `origin`.

See [AGENTS.md](AGENTS.md) for the project architecture and invariants, and
[LIBRARIES.md](LIBRARIES.md) for shared-library boundaries.
