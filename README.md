# Pawprints

Pawprints is a one-day MVP for private pet activity journaling. It supports email/password sessions, categories, dated Pawprint entries, restricted rich-text diary notes, private image uploads, search, personal activity counts, smoke verification, and a deterministic local demo seed.

## Architecture

The repository is split into a React/Vite frontend, one public Nginx gateway, and four synchronous FastAPI services: Auth, Event, Media, and Analytics. Browser traffic uses only `http://localhost:8080` and relative `/api/v1/*` paths. Auth, Event, Media, and Analytics ports stay private on the Docker Compose network, and each service validates JWTs itself.

Auth owns users, Argon2id passwords, RS256 access tokens, and rotating refresh cookies. Event owns categories, Pawprints, local-date timeline/search behavior, optimistic locking, and the read-only analytics view. Media owns private file metadata and storage under the persistent `media_data` volume. Analytics reads only the Event-owned view through a read-only PostgreSQL role and uses Redis as a degradable user-scoped cache.

## Prerequisites

- PowerShell 7 (`pwsh`)
- Docker Compose
- Node 22 is used inside disposable containers for frontend verification
- Python verification runs in service-isolated disposable Docker images; host Python packages are not required

## Local Workflow

Create `.env` and missing local secrets:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 setup
```

Start or rebuild the stack:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 up
```

Apply explicit service migrations:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 migrate
```

Run the reproducible test workflow:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 test
```

Run the public-boundary smoke:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke
```

Seed deterministic demo data only when you ask for it:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 seed
```

Stop containers without deleting data:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 down
```

`start` runs setup, infrastructure startup, migrations, application/monitoring startup, and smoke. `demo` runs `start` and then `seed`.

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 start
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 demo
```

`reset-data` is intentionally separate from `down` and currently fails until an explicitly destructive reset flow is implemented.

## Demo

Open the app at:

```text
http://localhost:8080
```

Default seeded demo credentials are local-only and can be overridden from ignored environment values:

```text
PAWPRINTS_DEMO_EMAIL=demo@pawprints.local
PAWPRINTS_DEMO_PASSWORD=demo123
PAWPRINTS_DEMO_ANCHOR_DATE=2026-09-13
```

The seed is repeatable. It reuses the demo user, avoids duplicate categories/events with deterministic `pawprints-demo-seed:v2:*` markers, creates five demo categories, creates ten synthetic Asia/Taipei Pawprints around the configured anchor date, uploads sample media through the normal authenticated Media API, and verifies Search, Timeline, and category-specific Analytics through Nginx.

If an older local database already contains `demo@pawprints.local` with a previous password, the seed will fail normal authentication rather than bypass Auth. Use a fresh local data set or override `PAWPRINTS_DEMO_EMAIL` for that run.

See [Demo Walkthrough](demo/README.md) for a short click path.

## Observability

Prometheus and Grafana are exposed locally:

```text
Prometheus: http://localhost:9090
Grafana: http://localhost:3000
```

Prometheus scrapes service `/metrics` endpoints internally. Nginx does not expose backend `/metrics` or `/internal/*` routes publicly.

## Compose Transparency

The script wraps ordinary Docker Compose commands with checked native exit codes:

```pwsh
docker compose up --build -d --wait
docker compose down
docker compose --profile jobs run --build --rm auth-migrate
docker compose --profile jobs run --build --rm event-migrate
docker compose --profile jobs run --build --rm media-migrate
docker compose --profile jobs run --build --rm smoke
docker compose --profile jobs run --build --rm seed
```

Tests use disposable containers and isolated `postgres-test`/`redis-test` infrastructure. Persistent demo data lives in `postgres_data`; uploaded files live in `media_data`. Normal `down` preserves both volumes.

## CI And Tradeoffs

GitHub Actions runs separate backend, frontend, infrastructure, and integration jobs. CI uses least-privilege read permissions, Node 22 for frontend checks, Docker/service-isolated backend tests, Compose validation, and the same Nginx public-boundary smoke.

MVP choices are intentionally narrow: synchronous FastAPI services, local filesystem media storage, PostgreSQL schemas per service, no OAuth/MFA/admin/RBAC, no object storage, and no production deployment pipeline.
