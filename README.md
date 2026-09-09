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

`uv run manage.py restore` restores locked dependencies without enforcing the
supported runtime version. `bootstrap` additionally enforces Node 22 for a fully
supported development checkout. Focused repository operations use
`restore --no-submodules` because they initialize only their selected monoapp.

Promote a mature monoapp from the shared monoapp controls, then create a
separately cloned workspace that retains only that app and disconnects it from
Xenorepo's remote:

```console
uv run manage.py monoapp promote app_name
uv run manage.py monoapp fork-workspace app_name
```

The routine removes the inherited `origin` after focusing the clone, then verifies
the detached workspace. Promotion defaults to the authenticated GitHub CLI account,
the monoapp name, and private visibility; explicit options can override those defaults.
If the app has not been promoted, `fork-workspace` offers to promote it with those
defaults. Pass `--directory` to override the default sibling directory.

See [AGENTS.md](AGENTS.md) for the project architecture and invariants, and
[LIBRARIES.md](LIBRARIES.md) for shared-library boundaries.
