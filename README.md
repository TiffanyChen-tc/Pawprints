# Pawprints

Pawprints is a one-day MVP monorepo with a React/Vite frontend, Nginx public gateway, and four FastAPI services: Auth, Event, Media, and Analytics.

## Prerequisites

- PowerShell 7 (`pwsh`)
- Docker Compose
- Python and Node.js for later host-run tests

## Local Workflow

Create local configuration and missing secrets:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 setup
```

Start the currently defined Compose services:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 up
```

The public browser and API boundary is Nginx at:

```text
http://localhost:8080
```

Local observability UIs are exposed at:

```text
Prometheus: http://localhost:9090
Grafana: http://localhost:3000
```

Auth, Event, Media, and Analytics service ports remain private on the Compose network. Their `/metrics` endpoints are scraped internally by Prometheus and are not exposed directly to the host.

Run migrations when service migration jobs exist:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 migrate
```

Run the test command surface:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 test
```

Run smoke and seed jobs when those job services exist:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 seed
```

Task 8 smoke exercises Auth, Event, private Media upload/list/retrieve, and Event-derived Analytics counts through Nginx only. It also verifies that Analytics requires Bearer authentication and internal service paths remain blocked. Auth, Event, Media, and Analytics service ports are intentionally private and are not exposed to the host.

Stop the stack without deleting persistent volumes:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 down
```

`reset-data` is intentionally separate from `down` and currently fails until an explicitly destructive reset flow is implemented.

## Compose Transparency

The script wraps ordinary Docker Compose commands. For Task 5, `up` maps to:

```pwsh
docker compose up --build -d --wait
```

`down` maps to:

```pwsh
docker compose down
```

Test dependencies use the `test` profile:

```pwsh
docker compose --profile test up --build -d --wait postgres-test redis-test
```

The persistent demo PostgreSQL volume is separate from test infrastructure. Test PostgreSQL and Redis are exposed only on loopback host ports for host-run tests.

Migration and smoke jobs use the `jobs` profile. Analytics has no service-owned MVP tables or migration job; it reads the Event-owned analytics view through its read-only PostgreSQL role.

```pwsh
docker compose --profile jobs run --build --rm auth-migrate
docker compose --profile jobs run --build --rm event-migrate
docker compose --profile jobs run --build --rm media-migrate
docker compose --profile jobs run --build --rm smoke
```

Uploaded media is stored in the persistent `media_data` volume mounted at `/var/lib/pawprints/media`. Normal `down` does not delete `postgres_data` or `media_data`.
