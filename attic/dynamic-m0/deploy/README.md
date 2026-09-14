# Deploy

A single-node Garleak stack on Docker Compose. Helm charts come later.

## Services

| Service | Image | Host port | Purpose |
|---------|-------|-----------|---------|
| `postgres` | `postgres:16-alpine` | none | Primary database |
| `redis` | `redis:7-alpine` | none | Celery broker and result backend |
| `typesense` | `typesense/typesense:30.2` | none | Search |
| `minio` | `quay.io/minio/minio` (pinned release) | 9001 (console, localhost only) | S3-compatible object storage |
| `api` | built from `apps/api` | 8000 | FastAPI. Runs `alembic upgrade head` on start. |
| `worker` | built from `apps/api` | none | Celery worker. Has one task, `garleak.ping`. |
| `web` | built from `apps/web` | 3000 | Next.js, server-rendered |

Every service has a healthcheck. The API waits for PostgreSQL, Redis, MinIO, and
Typesense to report healthy, and the web app waits for the API.

## First run

```sh
cd deploy
cp .env.example .env
```

Replace every `change-me` value in `.env`. For the session secret, run
`python -c "import secrets; print(secrets.token_urlsafe(48))"`.

To use ORCID login, register a client at the ORCID sandbox
(https://sandbox.orcid.org/developer-tools) with the redirect URI
`http://localhost:8000/auth/orcid/callback`, then put the client id and secret in `.env`.
Without them the stack still runs, and `/auth/orcid/login` returns 503.

```sh
docker compose config          # check the file and the interpolated values
docker compose up --build
```

Then check it.

```sh
curl http://localhost:8000/healthz
docker compose exec worker celery -A garleak_api.worker call garleak.ping
open http://localhost:3000
```

## Notes

- **Cookies in development.** The API sets the session cookie on `localhost:8000` and
  redirects to `localhost:3000` after login. Browsers scope cookies by host, not port, so
  this works locally. In production, serve both behind one origin with a reverse proxy.
- **MinIO image.** MinIO stopped publishing community images to Docker Hub in late 2025.
  The compose file pins the last community release from quay.io. Before production,
  decide whether to keep it, build from source, or switch to another S3-compatible store.
  The API only talks S3, so the swap is a config change.
- **Typesense healthcheck.** The image has no curl or wget, so the healthcheck opens a TCP
  connection with bash and reads the `/health` status line.
- **Buckets and collections** are not created yet. The API will create what it needs on
  startup once M1 stores anything.

## Production checklist

- `GARLEAK_ENV=production`. The API refuses to start without a session secret and with
  insecure cookies in that mode.
- `GARLEAK_SESSION_COOKIE_SECURE=true`, with HTTPS terminated at the proxy.
- `GARLEAK_ORCID_BASE_URL=https://orcid.org` and a production ORCID client.
- Do not expose PostgreSQL, Redis, Typesense, or MinIO ports publicly.
- Back up the `postgres-data` and `minio-data` volumes. v1 of every paper lives there and
  can never be regenerated.
