# Attic

Code that is no longer part of the build. It is kept in the repository so the reasoning
and the work stay on record, and so parts of it can be reused. Nothing here runs in CI,
and nothing outside this directory may import from it.

## dynamic-m0

The first milestone (M0) of the dynamic architecture that the master plan first
described. The layout is preserved exactly as it was at the repository root.

| Path | What it was |
|------|-------------|
| `dynamic-m0/apps/api` | FastAPI service on Python 3.12. Settings from `GARLEAK_*` variables, SQLAlchemy 2 and Alembic with one `accounts` migration, `/healthz`, ORCID authorization-code login against the sandbox, a Celery worker with a ping task. |
| `dynamic-m0/apps/web` | Next.js (App Router, TypeScript) site rendered on the server. Stub routes for `/`, `/list/`, `/scratch/list/`, and `/abs/`, a `robotsFor()` helper for `noindex`, and a branding check. |
| `dynamic-m0/deploy` | Docker Compose stack with PostgreSQL 16, Redis, Typesense, MinIO, the API, the worker, and the web app. |
| `dynamic-m0/packages/schema` | Placeholder for shared JSON Schemas, with a plan for generating Python and TypeScript models from them. |
| `dynamic-m0/ci-jobs.yml` | The `api` and `web` jobs removed from `.github/workflows/ci.yml`. Inert here, since GitHub only runs workflows under `.github/workflows/`. |

State on the day it was retired. The API had 20 passing tests and a clean ruff run. The
web app passed typecheck, lint, 9 unit tests, and a production build. The Compose file
was checked only against the compose-spec JSON Schema, because Docker was not installed.
ORCID login had only been tested with a mocked token exchange. CI had never run.

## Why it was retired

On 2026-09-14 the maintainer moved Garleak to a static architecture
([RFC 0001](../rfcs/0001-static-architecture.md)). The git repository is the database, a
Python generator in `site/` builds the HTML, and GitHub Pages serves it for free.
Submissions and verifications arrive as GitHub issue forms that Actions turn into pull
requests. A server, a database, a job queue, and object storage cost money every month and
need an operator, and nothing in Phase 1 needs them.

## What may be reused

- `apps/api/garleak_api/orcid.py` and its tests. The ORCID OAuth flow and token-response
  validation may inform the optional Phase 2 Cloudflare Worker, which would accept
  submissions behind ORCID sign-in and commit them with a bot token so that submitter
  identity stays private.
- `apps/web/lib/robots.ts` and `apps/web/lib/ids.ts`, with their tests. The `noindex` rule
  and the identifier parsing can be ported to the Python generator.
- `apps/web/scripts/check-branding.mjs`. The branding check (no "arxiv" string, no maroon)
  can be ported to the site checks.
- `packages/schema/README.md`. The plan for keeping schemas and generated models in step
  applies to the record format in `archive/` as well.

## Restoring it

Nothing here was committed before the move, so git history does not hold the old
locations. To restore, move the directories back and put the jobs from
`dynamic-m0/ci-jobs.yml` back into `.github/workflows/ci.yml` (with `api` and `web`
outputs and filters in the `changes` job).

```sh
git mv attic/dynamic-m0/apps attic/dynamic-m0/deploy .
git mv attic/dynamic-m0/packages/schema packages/
```

The root `.gitignore` also dropped the Next.js entries (`.next/`, `out/`,
`next-env.d.ts`, `*.tsbuildinfo`, `.eslintcache`). It keeps those patterns for paths under
`attic/`, so build output left in `apps/web` is still ignored.
