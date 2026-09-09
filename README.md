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

Stop the stack without deleting persistent volumes:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 down
```

`reset-data` is intentionally separate from `down` and currently fails until an explicitly destructive reset flow is implemented.

## Compose Transparency

The script wraps ordinary Docker Compose commands. For Task 1, `up` maps to:

```pwsh
docker compose up --build -d
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
