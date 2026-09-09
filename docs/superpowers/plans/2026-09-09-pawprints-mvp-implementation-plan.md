# Pawprints MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved Pawprints one-day MVP vertical slice end-to-end, then deepen the mandatory security, concurrency, observability, and smoke verification.

**Architecture:** Pawprints is a split monorepo with React/Vite frontend, Nginx public gateway, and four synchronous FastAPI services: Auth, Event, Media, and Analytics. Services communicate over explicit HTTP APIs on the private Docker Compose network, own their schemas/migrations, validate JWTs locally with shared RS256 verification code, and preserve object-level ownership.

**Tech Stack:** React, TypeScript, Vite, React Router, plain CSS, lucide-react, Python, FastAPI, Pydantic, SQLAlchemy, Alembic, httpx.Client, PostgreSQL, Redis, Pillow, pytest, Docker Compose, Nginx, Prometheus, Grafana, PowerShell 7 (`pwsh`).

**Spec:** `docs/superpowers/specs/2026-09-09-pawprints-mvp-design.md`

## Global Constraints

- Do not implement Future / MVP Non-Goal items from the spec.
- Do not create a worktree for this implementation unless the user later asks for one.
- Keep backend services deployable as separate containers under `services/auth`, `services/event`, `services/media`, and `services/analytics`.
- Keep `packages/pawprints-common` limited to JWT verification, internal service auth, authenticated identity, request/error helpers, narrow request-context/observability primitives, and focused tests.
- Use ordinary FastAPI `def` endpoints, synchronous SQLAlchemy Sessions, synchronous Alembic, reusable synchronous `httpx.Client` instances, and blocking Pillow image processing.
- Use RS256 access JWTs only. Auth issues with private key; Event, Media, and Analytics verify with public key.
- Use explicit JWT config consistently: `JWT_ISSUER=pawprints-auth`, `JWT_AUDIENCE=pawprints-api`, `ACCESS_TOKEN_TTL_MINUTES=15`.
- Use opaque refresh tokens, SHA-256 token hashes, Argon2id passwords, 7-day absolute refresh sessions, and refresh rotation on every successful refresh.
- Browser stores access JWT only in runtime memory. Never persist it in localStorage, sessionStorage, IndexedDB, URLs, or query strings.
- Refresh token is delivered only through an HttpOnly cookie scoped to `/api/v1/auth`, with Secure required in production and configurable for localhost.
- Nginx is the public API boundary. Browser API calls use relative `/api/v1/*` URLs. Backend service ports stay private to Compose.
- Private `/internal/*` service endpoints are not routed through Nginx and require per-caller static internal tokens plus endpoint authorization.
- Use one local PostgreSQL database with `auth`, `events`, and `media` schemas, least-privilege roles, and explicit per-service Alembic migration jobs.
- Configure service-owned Alembic version tables explicitly: `auth.alembic_version`, `events.alembic_version`, and `media.alembic_version`. Do not create or share `public.alembic_version`.
- Analytics reads only approved Event-owned analytics views through a read-only database role.
- Redis is used only as a degradable, user-scoped Analytics cache.
- Local media storage uses a `LocalFileStorage` adapter backed by a persistent Docker named volume or ignored host data directory; normal `down` does not delete DB or media data.
- All externally visible IDs are server-generated UUIDv4 values stored as PostgreSQL `uuid`.
- Mutable Events and Categories use integer `version` values and quoted integer ETags, for example `ETag: "1"` and `If-Match: "1"`.
- Event creation/update must verify any supplied `category_id` belongs to the authenticated user.
- Media public JSON must never expose `storage_key` or filesystem paths.
- Prometheus/Grafana are part of MVP; metrics labels must be low-cardinality and privacy-safe.
- Mandatory P0 security tests must be implemented early enough to guide service behavior, not as a final cosmetic pass.
- RED/GREEN commands must fail or pass because of Pawprints behavior, not missing dependencies. Each task that introduces a Python or frontend package first creates dependency metadata and installs dependencies before running its RED tests.
- PostgreSQL-specific behavior is tested against PostgreSQL, not SQLite. Integration tests use isolated test infrastructure such as `postgres-test` and `redis-test`, never the persistent demo/dev data volumes.

---

## File Structure Map

Create or modify these repository areas as tasks make them real:

- `compose.yaml`: full local stack, migration jobs, private services, Nginx, PostgreSQL, Redis, Prometheus, Grafana, persistent media volume.
- `.env.example`: committed safe configuration template with placeholders and non-secret defaults.
- `.gitignore`: ignored `.env`, generated keys, local secrets, local data directory if used, Python/Node build artifacts.
- `README.md`: transparent PowerShell 7 (`pwsh`) and Docker Compose workflow.
- `scripts/dev.ps1`: `setup`, `migrate`, `up`, `test`, `smoke`, `seed`, `down`, optional `start`/`demo`, explicit destructive reset only if added.
- `infra/postgres/init/001-bootstrap.sh`: database schemas, roles, and basic grants only.
- `infra/nginx/Dockerfile`: one public Nginx gateway image that builds and serves the React app and proxies `/api/v1/*`.
- `infra/nginx/nginx.conf`: same-origin frontend serving, `/api/v1/*` routing, header stripping, request IDs, JSON 413 response.
- `infra/prometheus/prometheus.yml`: internal service scrape targets.
- `infra/grafana/provisioning/datasources/prometheus.yml`: Prometheus datasource.
- `infra/grafana/provisioning/dashboards/dashboards.yml`: dashboard provider.
- `infra/grafana/dashboards/pawprints-service-overview.json`: RED dashboard.
- `packages/pawprints-common/pyproject.toml`
- `packages/pawprints-common/pawprints_common/jwt.py`
- `packages/pawprints-common/pawprints_common/internal_auth.py`
- `packages/pawprints-common/pawprints_common/errors.py`
- `packages/pawprints-common/pawprints_common/request_context.py`
- `packages/pawprints-common/tests/*`
- `services/auth/app/*`, `services/auth/tests/*`, `services/auth/migrations/*`, `services/auth/alembic.ini`, `services/auth/Dockerfile`, `services/auth/pyproject.toml`
- `services/event/app/*`, `services/event/tests/*`, `services/event/migrations/*`, `services/event/alembic.ini`, `services/event/Dockerfile`, `services/event/pyproject.toml`
- `services/media/app/*`, `services/media/tests/*`, `services/media/migrations/*`, `services/media/alembic.ini`, `services/media/Dockerfile`, `services/media/pyproject.toml`
- `services/analytics/app/*`, `services/analytics/tests/*`, `services/analytics/Dockerfile`, `services/analytics/pyproject.toml`
- `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/vite.config.ts`, `apps/web/src/*`
- `tests/smoke/pawprints_smoke.py`: whole-stack smoke through Nginx.
- `demo/seed.py` and optional `demo/assets/*`: API-driven seed data only.

---

## Dependency and Test Environment Contract

- Each Python package/service has its own `pyproject.toml` with runtime and test dependencies. Test extras include `pytest`, `pytest-cov`, `httpx`, and service-specific helpers.
- Every backend service image uses the repository root as Docker build context. Each Dockerfile copies and installs `packages/pawprints-common` first, then copies and installs the service package; common remains internal and unpublished.
- Local Python RED/GREEN commands run after installing dependencies with the service/package Python interpreter, for example `python -m pip install -e packages/pawprints-common[dev] -e services/auth[dev]` for Auth work.
- Service integration tests that need PostgreSQL, transactions, views, advisory locks, or concurrency run from the host against loopback-exposed `postgres-test` at `127.0.0.1:55432`, not SQLite and not the persistent demo database.
- Analytics cache tests run from the host against loopback-exposed `redis-test` at `127.0.0.1:56379` when Redis behavior matters. Pure cache-key formatting tests may run without Redis.
- Frontend RED/GREEN commands run after `npm ci` in `apps/web`, and `package-lock.json` is committed.
- Local RED/GREEN backend commands set explicit host-reachable test URLs before pytest, for example `AUTH_DATABASE_URL=postgresql+psycopg://pawprints_auth_rw:test_auth@127.0.0.1:55432/pawprints_test`; they must never connect to `postgres:5432/pawprints` or mutate persistent demo data.
- `dev.ps1 test` starts isolated test infrastructure, waits healthy, runs Auth/Event/Media migrations against `pawprints_test`, executes common/backend pytest suites against loopback test URLs, executes frontend tests that exist, tears down test containers/volumes for that test run, and preserves a nonzero exit code on failure.
- `dev.ps1` checks every required native command's exit code. Docker Compose, Python/Alembic/pytest, npm, smoke, start, migrate, and demo paths must never return exit code 0 after a required native command fails.
- Tests are host-runner tests. Do not add per-service Compose test-runner services unless the plan is explicitly revised later.

---

## Phase 1: Platform Spine and Security Primitives

### Task 1: Monorepo Skeleton, Config, and Dev Script Surface

**Files:**
- Create: `compose.yaml`
- Create: `.env.example`
- Modify: `.gitignore`
- Create: `README.md`
- Create: `scripts/dev.ps1`
- Create: `infra/postgres/init/001-bootstrap.sh`

**Interfaces:**
- Produces: directory layout, config variable names, PowerShell 7 (`pwsh`) task entrypoint, PostgreSQL schemas/roles.
- Later tasks consume: `JWT_ISSUER=pawprints-auth`, `JWT_AUDIENCE=pawprints-api`, per-service DB URLs, per-caller internal token env vars, `MEDIA_STORAGE_ROOT=/var/lib/pawprints/media`.

- [ ] **Step 1: Create skeleton directories**

Create only directories used by this task and the next immediate tasks:

```pwsh
New-Item -ItemType Directory -Force `
  packages/pawprints-common/pawprints_common, packages/pawprints-common/tests, `
  services/auth/app, services/auth/tests, services/auth/migrations/versions, `
  services/event/app, services/event/tests, services/event/migrations/versions, `
  services/media/app, services/media/tests, services/media/migrations/versions, `
  services/analytics/app, services/analytics/tests, `
  infra/postgres/init, scripts
```

- [ ] **Step 2: Update `.gitignore`**

Add these entries without removing user edits:

```gitignore
.env
.env.local
secrets/
data/
*.pyc
__pycache__/
.pytest_cache/
.ruff_cache/
node_modules/
dist/
coverage/
```

- [ ] **Step 3: Add `.env.example`**

Use safe placeholders and public defaults:

```dotenv
POSTGRES_DB=pawprints
POSTGRES_ADMIN_USER=postgres
POSTGRES_ADMIN_PASSWORD=CHANGE_ME
AUTH_DB_PASSWORD=CHANGE_ME
EVENT_DB_PASSWORD=CHANGE_ME
MEDIA_DB_PASSWORD=CHANGE_ME
ANALYTICS_DB_PASSWORD=CHANGE_ME

JWT_ISSUER=pawprints-auth
JWT_AUDIENCE=pawprints-api
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_SESSION_TTL_DAYS=7
JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public.pem

COOKIE_SECURE=false
COOKIE_SAMESITE=strict
COOKIE_DOMAIN=
AUTH_ALLOWED_ORIGINS=http://localhost:8080,http://localhost:5173

AUTH_DATABASE_URL=postgresql+psycopg://pawprints_auth_rw:CHANGE_ME@postgres:5432/pawprints
EVENT_DATABASE_URL=postgresql+psycopg://pawprints_event_rw:CHANGE_ME@postgres:5432/pawprints
MEDIA_DATABASE_URL=postgresql+psycopg://pawprints_media_rw:CHANGE_ME@postgres:5432/pawprints
ANALYTICS_DATABASE_URL=postgresql+psycopg://pawprints_analytics_ro:CHANGE_ME@postgres:5432/pawprints
TEST_AUTH_DATABASE_URL=postgresql+psycopg://pawprints_auth_rw:test_auth@127.0.0.1:55432/pawprints_test
TEST_EVENT_DATABASE_URL=postgresql+psycopg://pawprints_event_rw:test_event@127.0.0.1:55432/pawprints_test
TEST_MEDIA_DATABASE_URL=postgresql+psycopg://pawprints_media_rw:test_media@127.0.0.1:55432/pawprints_test
TEST_ANALYTICS_DATABASE_URL=postgresql+psycopg://pawprints_analytics_ro:test_analytics@127.0.0.1:55432/pawprints_test

REDIS_URL=redis://redis:6379/0
TEST_REDIS_URL=redis://127.0.0.1:56379/0
ANALYTICS_CACHE_TTL_SECONDS=600

MEDIA_STORAGE_ROOT=/var/lib/pawprints/media
MEDIA_MAX_IMAGES_PER_EVENT=5
MEDIA_MAX_FILE_BYTES=5242880
MEDIA_MAX_PIXELS=30000000

EVENT_SERVICE_URL=http://event:8000
MEDIA_SERVICE_URL=http://media:8000
ANALYTICS_SERVICE_URL=http://analytics:8000

EVENT_INTERNAL_TOKEN=CHANGE_ME_GENERATED
MEDIA_INTERNAL_TOKEN=CHANGE_ME_GENERATED
ANALYTICS_INTERNAL_TOKEN=CHANGE_ME_GENERATED
```

- [ ] **Step 4: Add PostgreSQL bootstrap shell wrapper**

`infra/postgres/init/001-bootstrap.sh` creates schemas and least-privilege roles deterministically during PostgreSQL first initialization. It invokes `psql` with explicit variables supplied by Compose environment. It creates schemas/roles/basic grants only; Event-owned analytics views and SELECT grants are created later by Event migrations after the view exists.

```sh
#!/usr/bin/env sh
set -eu

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${AUTH_DB_PASSWORD:?AUTH_DB_PASSWORD is required}"
: "${EVENT_DB_PASSWORD:?EVENT_DB_PASSWORD is required}"
: "${MEDIA_DB_PASSWORD:?MEDIA_DB_PASSWORD is required}"
: "${ANALYTICS_DB_PASSWORD:?ANALYTICS_DB_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v auth_db_password="$AUTH_DB_PASSWORD" \
  -v event_db_password="$EVENT_DB_PASSWORD" \
  -v media_db_password="$MEDIA_DB_PASSWORD" \
  -v analytics_db_password="$ANALYTICS_DB_PASSWORD" <<'SQL'
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS events;
CREATE SCHEMA IF NOT EXISTS media;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE ROLE pawprints_auth_rw LOGIN PASSWORD :'auth_db_password';
CREATE ROLE pawprints_event_rw LOGIN PASSWORD :'event_db_password';
CREATE ROLE pawprints_media_rw LOGIN PASSWORD :'media_db_password';
CREATE ROLE pawprints_analytics_ro LOGIN PASSWORD :'analytics_db_password';

GRANT USAGE, CREATE ON SCHEMA auth TO pawprints_auth_rw;
GRANT USAGE, CREATE ON SCHEMA events TO pawprints_event_rw;
GRANT USAGE, CREATE ON SCHEMA media TO pawprints_media_rw;
GRANT USAGE ON SCHEMA events TO pawprints_analytics_ro;
SQL
```

- [ ] **Step 5: Add initial Compose infrastructure and isolated test dependencies**

Create `compose.yaml` with persistent demo infrastructure and ephemeral test infrastructure:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_ADMIN_USER}
      POSTGRES_PASSWORD: ${POSTGRES_ADMIN_PASSWORD}
      AUTH_DB_PASSWORD: ${AUTH_DB_PASSWORD}
      EVENT_DB_PASSWORD: ${EVENT_DB_PASSWORD}
      MEDIA_DB_PASSWORD: ${MEDIA_DB_PASSWORD}
      ANALYTICS_DB_PASSWORD: ${ANALYTICS_DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/postgres/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d pawprints"]
      interval: 5s
      timeout: 3s
      retries: 20

  postgres-test:
    image: postgres:16-alpine
    profiles: ["test"]
    environment:
      POSTGRES_DB: pawprints_test
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      AUTH_DB_PASSWORD: test_auth
      EVENT_DB_PASSWORD: test_event
      MEDIA_DB_PASSWORD: test_media
      ANALYTICS_DB_PASSWORD: test_analytics
    tmpfs:
      - /var/lib/postgresql/data
    volumes:
      - ./infra/postgres/init:/docker-entrypoint-initdb.d:ro
    ports:
      - "127.0.0.1:55432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d pawprints_test"]
      interval: 5s
      timeout: 3s
      retries: 20

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20

  redis-test:
    image: redis:7-alpine
    profiles: ["test"]
    tmpfs:
      - /data
    ports:
      - "127.0.0.1:56379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20

volumes:
  postgres_data:
  media_data:
```

Later service tasks extend this Compose file with application services and one-shot job services. `postgres-test` and `redis-test` use the `test` profile, are reachable only through loopback host ports for host-run pytest, and never share the user's persistent demo data. Migration, smoke, and seed one-shot services use a non-default profile such as `jobs` so normal `dev.ps1 up` does not start them.

- [ ] **Step 6: Add real `scripts/dev.ps1` setup and command parser**

Create a PowerShell 7 script with explicit cases and a real setup flow. `setup` creates `.env` from `.env.example` when missing, generates only missing values, preserves existing credentials/keys, and never silently rotates secrets for an existing PostgreSQL volume.

```pwsh
param(
  [Parameter(Mandatory=$true)]
  [ValidateSet("setup","migrate","up","test","smoke","seed","down","start","demo","reset-data")]
  [string]$Command
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -lt 7) {
  throw "Pawprints dev workflow requires PowerShell 7+. Run this script with pwsh."
}

function Invoke-Checked {
  param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
  )
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Native command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
  }
}

function New-UrlSafeSecret {
  $bytes = [byte[]]::new(32)
  [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
  return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+","-").Replace("/","_")
}

function Set-EnvValueIfPlaceholder {
  param([string]$Path, [string]$Name, [string]$Value)
  $content = Get-Content $Path -Raw
  if ($content -match "(?m)^$Name=(CHANGE_ME|CHANGE_ME_GENERATED)$") {
    $content = $content -replace "(?m)^$Name=.*$", "$Name=$Value"
    Set-Content -Path $Path -Value $content -NoNewline
  }
}

function Ensure-LocalConfig {
  $volumeNames = & docker volume ls --format "{{.Name}}"
  if ($LASTEXITCODE -ne 0) {
    throw "Native command failed with exit code ${LASTEXITCODE}: docker volume ls --format {{.Name}}"
  }
  $volumeExists = ($volumeNames | Select-String -SimpleMatch "pawprints_postgres_data")
  if (!(Test-Path ".env") -and $volumeExists) {
    throw ".env is missing but the PostgreSQL volume exists. Restore .env or run an explicitly destructive reset before generating new DB credentials."
  }
  if (!(Test-Path ".env")) { Copy-Item ".env.example" ".env" }
  New-Item -ItemType Directory -Force "secrets" | Out-Null
  foreach ($name in "POSTGRES_ADMIN_PASSWORD","AUTH_DB_PASSWORD","EVENT_DB_PASSWORD","MEDIA_DB_PASSWORD","ANALYTICS_DB_PASSWORD","EVENT_INTERNAL_TOKEN","MEDIA_INTERNAL_TOKEN","ANALYTICS_INTERNAL_TOKEN") {
    Set-EnvValueIfPlaceholder ".env" $name (New-UrlSafeSecret)
  }
  $envContent = Get-Content ".env" -Raw
  foreach ($name in "AUTH","EVENT","MEDIA","ANALYTICS") {
    $password = [regex]::Match($envContent, "(?m)^${name}_DB_PASSWORD=(.+)$").Groups[1].Value
    $role = "pawprints_" + $name.ToLowerInvariant()
    if ($name -eq "ANALYTICS") { $role = "${role}_ro" } else { $role = "${role}_rw" }
    $urlName = "${name}_DATABASE_URL"
    $url = "postgresql+psycopg://${role}:${password}@postgres:5432/pawprints"
    $envContent = $envContent -replace "(?m)^$urlName=.*$", "$urlName=$url"
  }
  Set-Content -Path ".env" -Value $envContent -NoNewline

  if (!(Test-Path "secrets/jwt_private.pem") -or !(Test-Path "secrets/jwt_public.pem")) {
    $rsa = [System.Security.Cryptography.RSA]::Create(2048)
    $privatePem = [System.Text.Encoding]::ASCII.GetString($rsa.ExportPkcs8PrivateKeyPem())
    $publicPem = [System.Text.Encoding]::ASCII.GetString($rsa.ExportSubjectPublicKeyInfoPem())
    Set-Content -Path "secrets/jwt_private.pem" -Value $privatePem -NoNewline
    Set-Content -Path "secrets/jwt_public.pem" -Value $publicPem -NoNewline
  }
}

function Start-PresentServices {
  param([string[]]$Names)
  $services = & docker compose config --services
  if ($LASTEXITCODE -ne 0) {
    throw "Native command failed with exit code ${LASTEXITCODE}: docker compose config --services"
  }
  $present = @($Names | Where-Object { $services -contains $_ })
  if ($present.Count -gt 0) {
    Invoke-Checked docker compose up --build -d --wait @present
  }
}

function Wait-ForReady {
  Start-PresentServices @("auth","event","media","analytics","nginx","prometheus","grafana")
}

function Invoke-ComposeJobIfPresent {
  param([string]$ServiceName)
  $services = & docker compose config --services
  if ($LASTEXITCODE -ne 0) {
    throw "Native command failed with exit code ${LASTEXITCODE}: docker compose config --services"
  }
  if ($services -contains $ServiceName) {
    Invoke-Checked docker compose --profile jobs run --build --rm $ServiceName
  }
}

function Invoke-TestSuite {
  $exitCode = 0
  try {
    Invoke-Checked docker compose --profile test up --build -d --wait postgres-test redis-test

    $env:AUTH_DATABASE_URL = "postgresql+psycopg://pawprints_auth_rw:test_auth@127.0.0.1:55432/pawprints_test"
    $env:EVENT_DATABASE_URL = "postgresql+psycopg://pawprints_event_rw:test_event@127.0.0.1:55432/pawprints_test"
    $env:MEDIA_DATABASE_URL = "postgresql+psycopg://pawprints_media_rw:test_media@127.0.0.1:55432/pawprints_test"
    $env:ANALYTICS_DATABASE_URL = "postgresql+psycopg://pawprints_analytics_ro:test_analytics@127.0.0.1:55432/pawprints_test"
    $env:REDIS_URL = "redis://127.0.0.1:56379/0"

    Invoke-Checked python -m alembic -c services/auth/alembic.ini upgrade head
    Invoke-Checked python -m alembic -c services/event/alembic.ini upgrade head
    Invoke-Checked python -m alembic -c services/media/alembic.ini upgrade head

    Invoke-Checked python -m pytest packages/pawprints-common/tests services/auth/tests services/event/tests services/media/tests services/analytics/tests -q
    if (Test-Path "apps/web/package.json") {
      Invoke-Checked npm --prefix apps/web ci
      Invoke-Checked npm --prefix apps/web test -- --run
    }
  } catch {
    Write-Host $_
    $exitCode = 1
  } finally {
    & docker compose --profile test stop postgres-test redis-test
    if ($LASTEXITCODE -ne 0) { $exitCode = 1 }
    & docker compose --profile test rm -f postgres-test redis-test
    if ($LASTEXITCODE -ne 0) { $exitCode = 1 }
  }
  exit $exitCode
}

function Invoke-Migrate {
  foreach ($job in "auth-migrate","event-migrate","media-migrate") {
    Invoke-ComposeJobIfPresent $job
  }
}

function Invoke-Smoke {
  Wait-ForReady
  Invoke-Checked docker compose --profile jobs run --build --rm smoke
}

function Invoke-Seed {
  Invoke-Checked docker compose --profile jobs run --build --rm seed
}

function Invoke-Start {
  Ensure-LocalConfig
  Invoke-Checked docker compose up --build -d --wait postgres redis
  Invoke-Migrate
  Invoke-Smoke
}

function Invoke-Demo {
  Invoke-Start
  Invoke-Seed
}

switch ($Command) {
  "setup" { Ensure-LocalConfig }
  "migrate" { Invoke-Migrate }
  "up" { Invoke-Checked docker compose up --build -d }
  "test" { Invoke-TestSuite }
  "smoke" { Invoke-Smoke }
  "seed" { Invoke-Seed }
  "down" { Invoke-Checked docker compose down }
  "start" { Invoke-Start }
  "demo" { Invoke-Demo }
  "reset-data" {
    throw "Destructive reset is intentionally not implemented until explicitly requested during implementation."
  }
}
exit 0
```

- [ ] **Step 7: Verify shell surface**

Run: `pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 setup`

Expected: exits 0 under PowerShell 7+, creates `.env` and `secrets/jwt_private.pem` / `secrets/jwt_public.pem` when missing, replaces placeholder secrets with URL-safe generated values, aligns `*_DATABASE_URL` passwords with generated DB passwords, preserves existing generated values on repeated setup, and does not create seed data.

- [ ] **Step 8: Commit**

```bash
git add .gitignore .env.example README.md compose.yaml scripts/dev.ps1 infra/postgres/init/001-bootstrap.sh
git commit -m "chore: scaffold Pawprints local workflow"
```

### Task 2: Shared Security, Error, and Request Context Package

**Files:**
- Create: `packages/pawprints-common/pyproject.toml`
- Create: `packages/pawprints-common/pawprints_common/__init__.py`
- Create: `packages/pawprints-common/pawprints_common/jwt.py`
- Create: `packages/pawprints-common/pawprints_common/internal_auth.py`
- Create: `packages/pawprints-common/pawprints_common/errors.py`
- Create: `packages/pawprints-common/pawprints_common/request_context.py`
- Test: `packages/pawprints-common/tests/test_jwt.py`
- Test: `packages/pawprints-common/tests/test_internal_auth.py`
- Test: `packages/pawprints-common/tests/test_errors.py`

**Interfaces:**
- Produces: `verify_access_token(token: str, public_key_pem: str, issuer: str, audience: str) -> AuthenticatedUser`, `verify_internal_request(caller: str, token: str, allowed_callers: set[str], expected_tokens: Mapping[str, str]) -> InternalCaller`, `error_response(code: str, message: str, status_code: int, request_id: str, details: list[dict] | None = None) -> JSONResponse`.
- Consumes: RS256 public key, issuer `pawprints-auth`, audience `pawprints-api`.

- [ ] **Step 1: Create dependency metadata and install test dependencies**

Create `packages/pawprints-common/pyproject.toml` with runtime dependencies `fastapi`, `pyjwt[crypto]`, and test extra dependencies `pytest`, `httpx`, and `cryptography`. Create an empty `packages/pawprints-common/pawprints_common/__init__.py` so editable install succeeds before behavior modules exist. Then run:

```pwsh
python -m pip install -e "packages/pawprints-common[dev]"
```

Expected: dependency installation exits 0.

- [ ] **Step 2: Write failing JWT tests**

```python
def test_verify_access_token_accepts_rs256_with_expected_issuer_audience():
    claims = verify_access_token(valid_rs256_token, public_key_pem, "pawprints-auth", "pawprints-api")
    assert claims.user_id == user_id

def test_verify_access_token_rejects_wrong_audience():
    with pytest.raises(JWTValidationError):
        verify_access_token(token_with_wrong_audience, public_key_pem, "pawprints-auth", "pawprints-api")

def test_verify_access_token_rejects_expired_token():
    with pytest.raises(JWTValidationError):
        verify_access_token(expired_rs256_token, public_key_pem, "pawprints-auth", "pawprints-api")
```

- [ ] **Step 3: Verify RED**

Run: `python -m pytest packages/pawprints-common/tests/test_jwt.py -q`

Expected: FAIL because `pawprints_common.jwt` does not exist.

- [ ] **Step 4: Implement JWT verification**

Use `pyjwt[crypto]` or `python-jose[cryptography]`; keep algorithm fixed to `RS256`. Validate `iss`, `aud`, `exp`, and UUID-shaped `sub`. Return:

```python
@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
```

- [ ] **Step 5: Write and verify internal auth RED**

```python
def test_verify_internal_request_uses_constant_time_comparison(monkeypatch):
    called = False
    def fake_compare(left: str, right: str) -> bool:
        nonlocal called
        called = True
        return left == right
    monkeypatch.setattr(hmac, "compare_digest", fake_compare)
    caller = verify_internal_request("media-service", "token-a", {"media-service"}, {"media-service": "token-a"})
    assert caller.service_name == "media-service"
    assert called is True

def test_verify_internal_request_rejects_disallowed_endpoint_caller():
    with pytest.raises(InternalAuthError):
        verify_internal_request("auth-service", "token-a", {"media-service"}, {"auth-service": "token-a"})
```

Run: `python -m pytest packages/pawprints-common/tests/test_internal_auth.py -q`

Expected: FAIL before implementation.

- [ ] **Step 6: Implement internal auth and error envelope helpers**

Implement `hmac.compare_digest`, safe exceptions, and `error_response`. `error_response` always emits:

```json
{"error":{"code":"validation_failed","message":"Some fields are invalid.","request_id":"req-123"}}
```

- [ ] **Step 7: Verify GREEN**

Run: `python -m pytest packages/pawprints-common/tests -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add packages/pawprints-common
git commit -m "feat: add shared Pawprints security primitives"
```

---

## Phase 2: Auth and Event Vertical Slice Core

### Task 3: Auth Service with RS256 Access Tokens and Rotating Refresh Sessions

**Files:**
- Create: `services/auth/pyproject.toml`
- Create: `services/auth/Dockerfile`
- Create: `services/auth/alembic.ini`
- Create: `services/auth/migrations/env.py`
- Create: `services/auth/migrations/versions/0001_auth_tables.py`
- Create: `services/auth/app/config.py`
- Create: `services/auth/app/db.py`
- Create: `services/auth/app/models.py`
- Create: `services/auth/app/passwords.py`
- Create: `services/auth/app/tokens.py`
- Create: `services/auth/app/routes.py`
- Create: `services/auth/app/main.py`
- Test: `services/auth/tests/test_passwords.py`
- Test: `services/auth/tests/test_auth_api.py`
- Test: `services/auth/tests/test_refresh_rotation.py`

**Interfaces:**
- Produces public endpoints: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
- Produces JSON session shape: `{"access_token": str, "token_type": "Bearer", "expires_in": 900, "user": {"id": str, "email": str, "display_name": str | None}}`.
- Consumes common JWT config values `pawprints-auth` and `pawprints-api`, RS256 private key path, and `AUTH_ALLOWED_ORIGINS=http://localhost:8080,http://localhost:5173`.

- [ ] **Step 1: Create service dependency metadata and start isolated test database**

Create `services/auth/pyproject.toml` with runtime dependencies `fastapi`, `uvicorn`, `pydantic-settings`, `sqlalchemy`, `psycopg[binary]`, `alembic`, `pwdlib[argon2]`, and `pyjwt[crypto]`. Add test dependencies `pytest`, `httpx`, and `pytest-cov`. Do not put a portable relative editable dependency on `../../packages/pawprints-common` inside service metadata; install common explicitly in local and Docker workflows. Then run:

```pwsh
python -m pip install -e "packages/pawprints-common[dev]" -e "services/auth[dev]"
docker compose --profile test up --build -d --wait postgres-test
$env:AUTH_DATABASE_URL = "postgresql+psycopg://pawprints_auth_rw:test_auth@127.0.0.1:55432/pawprints_test"
```

Expected: dependencies install, `postgres-test` is healthy on `127.0.0.1:55432`, and Auth tests use the isolated `pawprints_test` database URL.

- [ ] **Step 2: Write password policy tests**

```python
def test_password_hash_verifies_and_is_not_plaintext():
    encoded = hash_password("correct horse battery")
    assert encoded != "correct horse battery"
    assert verify_password("correct horse battery", encoded) is True

def test_same_password_hashes_differ_due_to_random_salt():
    assert hash_password("correct horse battery") != hash_password("correct horse battery")

@pytest.mark.parametrize("password", ["", "   ", "short"])
def test_invalid_password_policy(password):
    with pytest.raises(PasswordPolicyError):
        validate_password(password)
```

Run with `$env:AUTH_DATABASE_URL` from Step 1 still set: `python -m pytest services/auth/tests/test_passwords.py -q`

Expected: FAIL before `passwords.py` exists.

- [ ] **Step 3: Implement Argon2id password handling**

Use `pwdlib.PasswordHash.recommended()` or equivalent Argon2id library API. Enforce exact policy: min 12, max 128, reject empty/all-whitespace, no composition rules, no trimming.

- [ ] **Step 4: Write Auth API tests**

Cover register/login/me/no-store/generic invalid credentials and explicit Origin allowlist for refresh/logout:

```python
def test_register_creates_session_sets_cookie_and_returns_access_token(client):
    response = client.post("/api/v1/auth/register", json={
        "email": " User@Example.COM ",
        "password": "correct horse battery",
        "display_name": "User"
    })
    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    assert "refresh_token=" in response.headers["set-cookie"]
    assert response.json()["token_type"] == "Bearer"
    assert response.json()["expires_in"] == 900
    assert response.json()["user"]["email"] == "user@example.com"

def test_refresh_rejects_origin_not_in_allowlist(client, registered_refresh_cookie):
    response = client.post("/api/v1/auth/refresh", headers={"Origin": "http://evil.example"}, cookies=registered_refresh_cookie)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"
```

- [ ] **Step 5: Write refresh rotation and concurrency tests**

```python
def test_refresh_rotates_and_old_refresh_token_is_rejected(client):
    login = register_and_capture_refresh_cookie(client)
    first = client.post("/api/v1/auth/refresh", headers={"Origin": "http://localhost:8080"}, cookies=login.cookies)
    second = client.post("/api/v1/auth/refresh", headers={"Origin": "http://localhost:8080"}, cookies=login.cookies)
    assert first.status_code == 200
    assert second.status_code == 401

def test_concurrent_refresh_allows_at_most_one_success(auth_db_session, refresh_token_value):
    results = run_two_refresh_transactions(refresh_token_value)
    assert sum(result.status_code == 200 for result in results) == 1
```

- [ ] **Step 6: Verify RED**

Run with `$env:AUTH_DATABASE_URL` from Step 1 still set: `python -m pytest services/auth/tests -q`

Expected: FAIL for missing endpoints/models.

- [ ] **Step 7: Implement Auth models, migration, routes, token issuance**

Use SQLAlchemy models for `auth.users` and `auth.refresh_tokens`. Configure `services/auth/migrations/env.py` with `version_table_schema="auth"` and `version_table="alembic_version"` so Auth owns `auth.alembic_version`. Hash refresh token with `hashlib.sha256(token.encode("utf-8")).hexdigest()`. Rotate with a PostgreSQL transaction that locks the presented refresh row, sets `revoked_at`, inserts replacement with the same `expires_at`, and stores `replaced_by_token_id`. Auth session endpoints validate `Origin` against `AUTH_ALLOWED_ORIGINS`, including both `http://localhost:8080` and Vite `http://localhost:5173`.

- [ ] **Step 8: Apply Auth migration to isolated test database**

Run with `$env:AUTH_DATABASE_URL` from Step 1 still set:

```pwsh
python -m alembic -c services/auth/alembic.ini upgrade head
```

Expected: migration exits 0 in the current isolated `pawprints_test` database, creates Auth tables in the `auth` schema, and records version state in `auth.alembic_version`, not `public.alembic_version`. Run this even if an earlier task or session already applied migrations elsewhere.

- [ ] **Step 9: Verify GREEN**

Run with `$env:AUTH_DATABASE_URL` from Step 1 still set: `python -m pytest services/auth/tests packages/pawprints-common/tests -q`

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add services/auth packages/pawprints-common
git commit -m "feat: add auth service"
```

### Task 4: Event Service Categories, Pawprints, Search, and Optimistic Locking

**Files:**
- Create: `services/event/pyproject.toml`
- Create: `services/event/Dockerfile`
- Create: `services/event/alembic.ini`
- Create: `services/event/migrations/env.py`
- Create: `services/event/migrations/versions/0001_event_tables.py`
- Create: `services/event/app/config.py`
- Create: `services/event/app/db.py`
- Create: `services/event/app/models.py`
- Create: `services/event/app/schemas.py`
- Create: `services/event/app/time_semantics.py`
- Create: `services/event/app/categories.py`
- Create: `services/event/app/events.py`
- Create: `services/event/app/search.py`
- Create: `services/event/app/internal.py`
- Create: `services/event/app/clients.py`
- Create: `services/event/app/main.py`
- Test: `services/event/tests/test_time_semantics.py`
- Test: `services/event/tests/test_category_api.py`
- Test: `services/event/tests/test_event_api.py`
- Test: `services/event/tests/test_event_security.py`
- Test: `services/event/tests/test_optimistic_locking.py`
- Test: `services/event/tests/test_search.py`

**Interfaces:**
- Produces public endpoints under `/api/v1/categories` and `/api/v1/events`.
- Produces internal endpoint `GET /internal/events/{event_id}/ownership`.
- Consumes shared `verify_access_token` and `verify_internal_request`.
- Consumes Analytics invalidation client interface: `invalidate_user_analytics(user_id: UUID, request_id: str) -> None`.

- [ ] **Step 1: Create service dependency metadata and start isolated test database**

Create `services/event/pyproject.toml` with runtime dependencies `fastapi`, `uvicorn`, `pydantic-settings`, `sqlalchemy`, `psycopg[binary]`, `alembic`, and `httpx`. Add test dependencies `pytest`, `httpx`, and `pytest-cov`. Do not put a portable relative editable dependency on `../../packages/pawprints-common` inside service metadata; install common explicitly in local and Docker workflows. Then run:

```pwsh
python -m pip install -e "packages/pawprints-common[dev]" -e "services/event[dev]"
docker compose --profile test up --build -d --wait postgres-test
$env:EVENT_DATABASE_URL = "postgresql+psycopg://pawprints_event_rw:test_event@127.0.0.1:55432/pawprints_test"
```

Expected: dependencies install, `postgres-test` is healthy on `127.0.0.1:55432`, and Event tests use the isolated `pawprints_test` database URL.

- [ ] **Step 2: Write time and validation tests**

```python
def test_local_datetime_timezone_derives_utc_and_local_date():
    result = derive_event_time("2026-09-09T23:30:00", "Asia/Taipei")
    assert result.local_date.isoformat() == "2026-09-09"
    assert result.occurred_at.tzinfo is not None

def test_invalid_timezone_rejected():
    with pytest.raises(EventValidationError):
        derive_event_time("2026-09-09T12:00:00", "Not/AZone")
```

Run with `$env:EVENT_DATABASE_URL` from Step 1 still set: `python -m pytest services/event/tests/test_time_semantics.py -q`

Expected: FAIL before implementation.

- [ ] **Step 3: Implement time semantics**

Use Python `zoneinfo.ZoneInfo`. Accept local datetime input without trusting client-supplied `local_date`. Return canonical UTC `occurred_at`, validated `timezone`, and derived `local_date`.

- [ ] **Step 4: Write category tests**

Cover list/create/rename, normalized duplicate prevention, quoted ETag, stale `If-Match`, and cross-user rename returning 404.

```python
def test_category_duplicate_is_case_insensitive_per_user(client, user_token):
    create_category(client, user_token, "Running")
    response = create_category(client, user_token, " running ")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "category_name_exists"
```

- [ ] **Step 5: Write Event ownership and foreign category tests**

```python
def test_user_b_cannot_create_event_with_user_a_category(client, token_a, token_b, category_a):
    response = client.post("/api/v1/events", headers=bearer(token_b), json=valid_event_body(category_id=str(category_a.id)))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"

def test_user_b_cannot_patch_own_event_to_user_a_category(client, token_b, event_b, category_a):
    response = client.patch(
        f"/api/v1/events/{event_b.id}",
        headers={**bearer(token_b), "If-Match": '"1"'},
        json={"category_id": str(category_a.id)}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"
```

- [ ] **Step 6: Write optimistic locking tests**

```python
def test_patch_requires_if_match(client, token_a, event_a):
    response = client.patch(f"/api/v1/events/{event_a.id}", headers=bearer(token_a), json={"title": "Changed"})
    assert response.status_code == 428

def test_stale_if_match_returns_412_without_leaking_foreign_versions(client, token_a, event_a):
    patch_event(client, token_a, event_a.id, if_match='"1"', body={"title": "First"})
    stale = patch_event(client, token_a, event_a.id, if_match='"1"', body={"title": "Second"})
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "stale_version"
```

- [ ] **Step 7: Write Search and Timeline tests**

```python
def test_timeline_orders_by_occurred_at_ascending(client, token_a, category_a):
    create_event(client, token_a, category_a.id, "Morning", "2026-09-09T08:00:00")
    create_event(client, token_a, category_a.id, "Evening", "2026-09-09T18:00:00")
    response = client.get("/api/v1/events/timeline?date=2026-09-09", headers=bearer(token_a))
    assert [item["title"] for item in response.json()["items"]] == ["Morning", "Evening"]

def test_search_is_user_scoped_at_query_level(client, token_a, token_b, category_a, category_b):
    create_event(client, token_a, category_a.id, "Private needle", "2026-09-09T10:00:00")
    response = client.get("/api/v1/events/search?keyword=needle", headers=bearer(token_b))
    assert response.json()["items"] == []
```

- [ ] **Step 8: Verify RED**

Run with `$env:EVENT_DATABASE_URL` from Step 1 still set: `python -m pytest services/event/tests -q`

Expected: FAIL for missing Event service implementation.

- [ ] **Step 9: Implement Event models, migrations, routes, analytics view**

Implement `events.categories`, `events.events`, and the final Event-owned analytics view in `services/event/migrations/versions/0001_event_tables.py` before Task 5 applies this migration. Configure `services/event/migrations/env.py` with `version_table_schema="events"` and `version_table="alembic_version"` so Event owns `events.alembic_version`. The analytics view is strictly least privilege for MVP activity counts and exposes only `event_id`, `user_id`, `category_id`, `category_name`, and `local_date`. Grant SELECT on that view to `pawprints_analytics_ro` in this migration. Register `/events/timeline` and `/events/search` before `/events/{event_id}`. Use atomic `UPDATE ... WHERE id = :id AND user_id = :user_id AND version = :expected_version RETURNING ...` semantics through SQLAlchemy.

- [ ] **Step 10: Implement internal ownership check and Analytics invalidation client**

`GET /internal/events/{event_id}/ownership` requires Media internal credentials plus forwarded Bearer JWT. Event Service validates both, checks ownership, and returns 200 for owned or 404 for missing/foreign. The Analytics invalidation client uses reusable `httpx.Client` with request ID and Event internal token; failures are logged without rolling back Event mutations.

- [ ] **Step 11: Apply Event migration to isolated test database**

Run with `$env:EVENT_DATABASE_URL` from Step 1 still set:

```pwsh
python -m alembic -c services/event/alembic.ini upgrade head
```

Expected: migration exits 0 in the current isolated `pawprints_test` database, creates Event-owned tables and `events.analytics_event_facts`, grants only view SELECT to `pawprints_analytics_ro`, and records version state in `events.alembic_version`, not `public.alembic_version`. Run this even if an earlier task or session already applied migrations elsewhere.

- [ ] **Step 12: Verify GREEN**

Run with `$env:EVENT_DATABASE_URL` from Step 1 still set: `python -m pytest services/event/tests packages/pawprints-common/tests -q`

Expected: PASS.

- [ ] **Step 13: Commit**

```bash
git add services/event packages/pawprints-common
git commit -m "feat: add event service core"
```

### Task 5: Compose, Nginx, and Partial Vertical Slice Smoke for Auth + Event

**Files:**
- Modify: `compose.yaml`
- Create: `apps/web/package.json`
- Create: `apps/web/package-lock.json`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
- Create: `infra/nginx/Dockerfile`
- Create: `infra/nginx/nginx.conf`
- Modify: `scripts/dev.ps1`
- Create: `tests/smoke/pawprints_smoke.py`
- Modify: `README.md`

**Interfaces:**
- Produces Nginx public routes for `/api/v1/auth/*`, `/api/v1/events/*`, and `/api/v1/categories/*`.
- Produces smoke helper functions `register_user`, `login_user`, `create_category`, `create_event`, `get_timeline`.

- [ ] **Step 1: Add Compose services, healthchecks, test infrastructure, and migration jobs**

Extend the Compose infrastructure from Task 1 with private `auth`, `event`, and `nginx` services plus `auth-migrate`, `event-migrate`, and `smoke`. Put migration and smoke services under `profiles: ["jobs"]`. Do not add backend test-runner services for host-run pytest. Do not expose `auth` or `event` ports to the host. Expose only Nginx and demo observability ports. Add Compose healthchecks for Auth, Event, and Nginx so `docker compose up --build -d --wait ...` blocks until services are healthy.

- [ ] **Step 2: Configure Nginx routing**

Use one public Nginx gateway and preserve the original `/api/v1` URI when proxying. Cover exact collection paths and nested paths separately:

```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  add_header X-Request-Id $request_id always;

  proxy_set_header Host $host;
  proxy_set_header Authorization $http_authorization;
  proxy_set_header Cookie $http_cookie;
  proxy_set_header X-Request-Id $request_id;
  proxy_set_header X-User-Id "";
  proxy_set_header X-Pawprints-Internal-Service "";
  proxy_set_header X-Pawprints-Internal-Token "";

  location = /api/v1/auth { proxy_pass http://auth:8000; }
  location /api/v1/auth/ { proxy_pass http://auth:8000; }

  location = /api/v1/categories { proxy_pass http://event:8000; }
  location /api/v1/categories/ { proxy_pass http://event:8000; }

  location = /api/v1/events { proxy_pass http://event:8000; }
  location /api/v1/events/ { proxy_pass http://event:8000; }

  location /internal/ { return 404; }

  location / {
    try_files $uri /index.html;
  }
}
```

Generate or normalize the public request ID at Nginx with `$request_id`, forward that value as `X-Request-Id`, and return it as an `X-Request-Id` response header. Forward `Authorization`, `Cookie`, and `Set-Cookie`. Strip `X-User-Id`, `X-Pawprints-Internal-Service`, and `X-Pawprints-Internal-Token` from public requests.

- [ ] **Step 3: Add minimal frontend build input**

Create a tiny Vite React shell that renders "Pawprints" at `/` so the production/demo gateway can build and serve a real React artifact before the full UI is implemented. Run:

```pwsh
cd apps/web
npm install
cd ../..
```

Expected: `apps/web/package-lock.json` exists and is committed. Later frontend tasks modify this app instead of creating a second production serving model.

- [ ] **Step 4: Add production/demo Nginx image with React build stage**

Create `infra/nginx/Dockerfile` as the single production serving model:

```dockerfile
FROM node:22-alpine AS web-build
WORKDIR /repo/apps/web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=web-build /repo/apps/web/dist /usr/share/nginx/html
COPY infra/nginx/nginx.conf /etc/nginx/conf.d/default.conf
```

- [ ] **Step 5: Write partial smoke test**

`tests/smoke/pawprints_smoke.py`:

```python
def test_auth_event_timeline_smoke(gateway_url):
    session = requests.Session()
    home = session.get(f"{gateway_url}/")
    assert home.status_code == 200
    assert "Pawprints" in home.text
    auth = register_user(session, gateway_url, unique_email(), "correct horse battery")
    category = create_category(session, gateway_url, auth.access_token, "Running")
    event = create_event(session, gateway_url, auth.access_token, category["id"], title="Morning run")
    timeline = get_timeline(session, gateway_url, auth.access_token, event["local_date"])
    assert [item["id"] for item in timeline["items"]] == [event["id"]]
```

- [ ] **Step 6: Verify RED**

Run: `pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke`

Expected: FAIL before Compose/Nginx stack is fully wired.

- [ ] **Step 7: Wire `dev.ps1 migrate`, `up`, `smoke`, and `down`**

`migrate` runs only explicit job-profile migration services and stops on failure. `smoke` first rebuilds/starts the current app services through `Wait-ForReady`, then runs the job-profile smoke container. `down` runs `docker compose down` and does not remove volumes.

- [ ] **Step 8: Verify GREEN**

Run:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 setup
docker compose up --build -d --wait postgres redis
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 migrate
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 up
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke
```

Expected: smoke test passes through Nginx, `GET /` returns the Pawprints frontend/index, exact collection endpoints work, nested resource endpoints work, internal routes are not public, and no backend service port is exposed to the browser/host.

- [ ] **Step 9: Commit**

```bash
git add compose.yaml apps/web infra/nginx/Dockerfile infra/nginx/nginx.conf scripts/dev.ps1 tests/smoke README.md
git commit -m "chore: wire auth event stack through nginx"
```

---

## Phase 3: Media and Private Images

### Task 6: Media Service Upload, Private Retrieval, Ordering, and Cleanup

**Files:**
- Create: `services/media/pyproject.toml`
- Create: `services/media/Dockerfile`
- Create: `services/media/alembic.ini`
- Create: `services/media/migrations/env.py`
- Create: `services/media/migrations/versions/0001_media_tables.py`
- Create: `services/media/app/config.py`
- Create: `services/media/app/db.py`
- Create: `services/media/app/models.py`
- Create: `services/media/app/storage.py`
- Create: `services/media/app/image_processing.py`
- Create: `services/media/app/event_client.py`
- Create: `services/media/app/routes.py`
- Create: `services/media/app/internal.py`
- Create: `services/media/app/main.py`
- Test: `services/media/tests/test_image_processing.py`
- Test: `services/media/tests/test_media_api.py`
- Test: `services/media/tests/test_media_security.py`
- Test: `services/media/tests/test_media_compensation.py`

**Interfaces:**
- Produces public endpoints: `POST /api/v1/media/events/{event_id}`, `GET /api/v1/media/events/{event_id}`, `GET /api/v1/media/{media_id}`, `DELETE /api/v1/media/{media_id}`.
- Produces internal endpoint: `POST /internal/media/events/{event_id}/cleanup`.
- Consumes Event ownership endpoint with Media internal credentials and forwarded user JWT.
- Produces `LocalFileStorage.write(key: str, content: bytes) -> None`, `read(key: str) -> Iterator[bytes]`, `delete(key: str) -> None`.

- [ ] **Step 1: Create service dependency metadata and start isolated test infrastructure**

Create `services/media/pyproject.toml` with runtime dependencies `fastapi`, `uvicorn`, `pydantic-settings`, `sqlalchemy`, `psycopg[binary]`, `alembic`, `httpx`, `pillow`, and `python-multipart`. Add test dependencies `pytest`, `httpx`, and `pytest-cov`. Do not put a portable relative editable dependency on `../../packages/pawprints-common` inside service metadata; install common explicitly in local and Docker workflows. Then run:

```pwsh
python -m pip install -e "packages/pawprints-common[dev]" -e "services/media[dev]"
docker compose --profile test up --build -d --wait postgres-test
$env:MEDIA_DATABASE_URL = "postgresql+psycopg://pawprints_media_rw:test_media@127.0.0.1:55432/pawprints_test"
```

Expected: dependencies install, `postgres-test` is healthy on `127.0.0.1:55432`, and Media tests use the isolated `pawprints_test` database URL.

- [ ] **Step 2: Write image validation tests**

```python
def test_jpeg_png_webp_are_decoded_and_reencoded_without_exif(sample_jpeg_with_exif):
    result = normalize_image(sample_jpeg_with_exif, max_bytes=5_242_880, max_pixels=30_000_000)
    assert result.mime_type == "image/jpeg"
    assert result.bytes != sample_jpeg_with_exif

def test_corrupt_file_is_rejected():
    with pytest.raises(InvalidImageError):
        normalize_image(b"not an image", max_bytes=5_242_880, max_pixels=30_000_000)

def test_animated_webp_is_rejected(animated_webp_bytes):
    with pytest.raises(InvalidImageError):
        normalize_image(animated_webp_bytes, max_bytes=5_242_880, max_pixels=30_000_000)
```

- [ ] **Step 3: Verify RED**

Run: `python -m pytest services/media/tests/test_image_processing.py -q`

Expected: FAIL before image processing exists.

- [ ] **Step 4: Implement Pillow normalization**

Use `Image.open`, `Image.verify` or full decode, `ImageOps.exif_transpose`, `Image.n_frames` for animation rejection, `Image.MAX_IMAGE_PIXELS` left enabled, explicit pixel count check, and re-encode JPEG/PNG/WebP to metadata-stripped bytes.

- [ ] **Step 5: Write media count/order/security tests**

```python
def test_upload_appends_display_order_and_preserves_batch_order(client, token_a, event_a, image_files):
    first = upload_images(client, token_a, event_a.id, image_files[:2])
    second = upload_images(client, token_a, event_a.id, image_files[2:4])
    assert [m["display_order"] for m in first.json()] == [1, 2]
    assert [m["display_order"] for m in second.json()] == [3, 4]

def test_user_b_cannot_upload_media_to_user_a_event(client, token_b, event_a, image_file):
    response = upload_images(client, token_b, event_a.id, [image_file])
    assert response.status_code == 404

def test_public_media_json_does_not_expose_storage_key_or_path(client, token_a, event_a, image_file):
    response = upload_images(client, token_a, event_a.id, [image_file])
    body = response.json()[0]
    assert "storage_key" not in body
    assert "path" not in body
```

- [ ] **Step 6: Write compensation tests**

```python
def test_metadata_failure_deletes_previously_written_files(media_service, storage, event_a, image_file, monkeypatch):
    monkeypatch.setattr(media_service.repository, "insert_media_batch", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db failed")))
    with pytest.raises(RuntimeError):
        media_service.upload(event_a.id, [image_file], user_token)
    assert storage.list_keys() == []

def test_concurrent_limit_rejection_deletes_normalized_temp_files(media_service, storage, event_with_four_media, two_image_files):
    response = media_service.upload(event_with_four_media.id, two_image_files, user_token)
    assert response.error_code == "media_limit_exceeded"
    assert storage.count_new_files_for_event(event_with_four_media.id) == 0

def test_two_concurrent_uploads_from_four_existing_media_allow_at_most_one(client, token_a, event_with_four_media, image_file_factory, storage):
    results = run_two_concurrent_upload_requests(
        lambda: upload_images(client, token_a, event_with_four_media.id, [image_file_factory()])
    )
    assert sum(result.status_code == 201 for result in results) == 1
    assert count_media_rows(event_with_four_media.id) == 5
    display_orders = list_display_orders(event_with_four_media.id)
    assert len(display_orders) == len(set(display_orders))
    assert storage.count_normalized_or_stored_files_without_metadata(event_with_four_media.id) == 0
```

- [ ] **Step 7: Verify RED**

Run: `python -m pytest services/media/tests -q`

Expected: FAIL before Media routes/storage/DB exist.

- [ ] **Step 8: Implement Media metadata migration and LocalFileStorage**

Create `media.event_media` with UUID id, event_id, storage_key, mime_type, file_size, display_order, created_at, and unique `(event_id, display_order)`. Configure `services/media/migrations/env.py` with `version_table_schema="media"` and `version_table="alembic_version"` so Media owns `media.alembic_version`. Store files under `MEDIA_STORAGE_ROOT` using generated keys. Use a persistent Compose volume mounted at `/var/lib/pawprints/media`.

- [ ] **Step 9: Implement upload transaction and cleanup**

Decode/normalize first into temporary in-memory or temporary file objects outside the short DB critical section. Enter a short DB transaction, acquire per-event PostgreSQL transaction advisory lock, recount media, reject `existing + incoming > 5`, assign display_order values, write files, insert metadata, commit. If the five-image limit rejects the batch after temporary normalization, delete temporary files. If any storage write succeeds and any later storage or metadata step fails, best-effort delete every newly written file before returning a safe error. The real concurrent upload regression above must pass because the advisory lock serializes per-Event count/order decisions.

- [ ] **Step 10: Implement private retrieval and deletion**

Every list/retrieve/delete path verifies Event ownership through Event Service. Stream bytes only after authz. Deletion hard-deletes metadata and file and never renumbers display order.

- [ ] **Step 11: Implement idempotent internal cleanup**

`POST /internal/media/events/{event_id}/cleanup` requires Event internal credentials, deletes all files and metadata for the Event, and returns success even when no media remain.

- [ ] **Step 12: Apply Media migration to isolated test database**

Run with `$env:MEDIA_DATABASE_URL` from Step 1 still set:

```pwsh
python -m alembic -c services/media/alembic.ini upgrade head
```

Expected: migration exits 0 in the current isolated `pawprints_test` database, creates Media tables in the `media` schema, and records version state in `media.alembic_version`, not `public.alembic_version`. Run this even if an earlier task or session already applied migrations elsewhere.

- [ ] **Step 13: Verify GREEN**

Run with `$env:MEDIA_DATABASE_URL` from Step 1 still set: `python -m pytest services/media/tests services/event/tests/test_event_security.py packages/pawprints-common/tests -q`

Expected: PASS.

- [ ] **Step 14: Commit**

```bash
git add services/media compose.yaml
git commit -m "feat: add private media service"
```

### Task 7: Integrate Media Through Nginx and Extend Smoke Slice

**Files:**
- Modify: `compose.yaml`
- Modify: `infra/nginx/nginx.conf`
- Modify: `tests/smoke/pawprints_smoke.py`
- Modify: `scripts/dev.ps1`
- Modify: `README.md`

**Interfaces:**
- Extends public route `/api/v1/media/*`.
- Extends smoke helper `upload_images` and `list_media`.

- [ ] **Step 1: Add Media service, migration job, and storage volume to Compose**

Mount persistent media volume:

```yaml
volumes:
  postgres_data:
  media_data:

services:
  media:
    volumes:
      - media_data:/var/lib/pawprints/media
```

Add `media-migrate` under `profiles: ["jobs"]`. Do not add a backend test-runner service; Media tests run from the host against `postgres-test`.

- [ ] **Step 2: Add Nginx Media routing and body limit**

Configure exact and nested Media routes while preserving the original URI:

```nginx
location = /api/v1/media { client_max_body_size 30m; proxy_pass http://media:8000; }
location /api/v1/media/ { client_max_body_size 30m; proxy_pass http://media:8000; }
```

Return JSON for Nginx-generated 413 responses where practical. Continue stripping internal headers and keep `/internal/*` inaccessible publicly.

- [ ] **Step 3: Extend smoke**

Add upload/list/retrieve assertions:

```python
media = upload_images(session, gateway_url, auth.access_token, event["id"], [small_png(), small_jpeg()])
assert [item["display_order"] for item in media] == [1, 2]
listed = list_media(session, gateway_url, auth.access_token, event["id"])
assert [item["id"] for item in listed] == [item["id"] for item in media]
image = fetch_media_bytes(session, gateway_url, auth.access_token, media[0]["id"])
assert image.startswith(b"\x89PNG") or image.startswith(b"\xff\xd8")
```

- [ ] **Step 4: Verify full Auth/Event/Media vertical segment**

Run:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 migrate
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke
```

Expected: smoke passes through Nginx, media bytes require Bearer auth, normal `down` does not remove `media_data`.

- [ ] **Step 5: Commit**

```bash
git add compose.yaml infra/nginx/nginx.conf tests/smoke scripts/dev.ps1 README.md
git commit -m "chore: route private media through gateway"
```

---

## Phase 4: Analytics, Redis, and Deletion Semantics

### Task 8: Analytics Service with Read-Only Event View and Degradable Redis Cache

**Files:**
- Create: `services/analytics/pyproject.toml`
- Create: `services/analytics/Dockerfile`
- Create: `services/analytics/app/config.py`
- Create: `services/analytics/app/db.py`
- Create: `services/analytics/app/cache.py`
- Create: `services/analytics/app/routes.py`
- Create: `services/analytics/app/internal.py`
- Create: `services/analytics/app/main.py`
- Modify: `compose.yaml`
- Modify: `infra/nginx/nginx.conf`
- Test: `services/analytics/tests/test_activity_counts.py`
- Test: `services/analytics/tests/test_cache.py`
- Test: `services/analytics/tests/test_security.py`
- Test: `services/analytics/tests/test_redis_degraded.py`

**Interfaces:**
- Produces public endpoint `GET /api/v1/analytics/activity-counts?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&grouping=none|week|month`.
- Produces internal endpoint `POST /internal/analytics/users/{user_id}/invalidate`.
- Consumes read-only `events.analytics_event_facts` view.
- Produces cache helpers `cache_key(user_id: UUID, version: int, query: ActivityQuery) -> str` and `invalidate_user(user_id: UUID) -> None`.

- [ ] **Step 1: Create service dependency metadata and start isolated test infrastructure**

Create `services/analytics/pyproject.toml` with runtime dependencies `fastapi`, `uvicorn`, `pydantic-settings`, `sqlalchemy`, `psycopg[binary]`, and `redis`. Add test dependencies `pytest`, `httpx`, and `pytest-cov`. Do not put a portable relative editable dependency on `../../packages/pawprints-common` inside service metadata; install common explicitly in local and Docker workflows. Then run:

```pwsh
python -m pip install -e "packages/pawprints-common[dev]" -e "services/analytics[dev]"
docker compose --profile test up --build -d --wait postgres-test redis-test
$env:EVENT_DATABASE_URL = "postgresql+psycopg://pawprints_event_rw:test_event@127.0.0.1:55432/pawprints_test"
$env:ANALYTICS_DATABASE_URL = "postgresql+psycopg://pawprints_analytics_ro:test_analytics@127.0.0.1:55432/pawprints_test"
$env:REDIS_URL = "redis://127.0.0.1:56379/0"
```

Expected: dependencies install, `postgres-test` is healthy on `127.0.0.1:55432`, `redis-test` is healthy on `127.0.0.1:56379`, and Analytics tests use isolated test URLs.

- [ ] **Step 2: Write analytics user-scope and grouping tests**

```python
def test_activity_counts_group_by_category_for_authenticated_user(client, token_a, facts_for_two_users):
    response = client.get("/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30", headers=bearer(token_a))
    assert response.json()["items"] == [{"category_id": str(facts_for_two_users.a_category_id), "category_name": "Running", "count": 2}]
    assert facts_for_two_users.b_category_id not in {UUID(item["category_id"]) for item in response.json()["items"]}

def test_weekly_grouping_uses_iso_monday_buckets(client, token_a, facts):
    response = client.get("/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30&grouping=week", headers=bearer(token_a))
    assert response.json()["buckets"][0]["bucket_start_date"] == "2026-08-31"
```

- [ ] **Step 3: Write Redis cache tests**

```python
def test_cache_key_is_user_scoped_and_versioned():
    key_a = cache_key(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), 4, ActivityQuery(start_date=date(2026,9,1), end_date=date(2026,9,30)))
    key_b = cache_key(UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"), 4, ActivityQuery(start_date=date(2026,9,1), end_date=date(2026,9,30)))
    assert key_a != key_b
    assert ":user:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa:" in key_a
    assert ":ver:4:" in key_a

def test_invalidation_increments_user_version(redis_client, user_id):
    before = get_user_cache_version(redis_client, user_id)
    invalidate_user(redis_client, user_id)
    assert get_user_cache_version(redis_client, user_id) == before + 1
```

- [ ] **Step 4: Write Redis degraded fallback tests**

```python
def test_redis_unavailable_queries_postgres_and_marks_cache_degraded(client, token_a, monkeypatch):
    monkeypatch.setattr(cache_module, "get_cached_result", lambda *args, **kwargs: (_ for _ in ()).throw(RedisError("down")))
    response = client.get("/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30", headers=bearer(token_a))
    assert response.status_code == 200
    assert analytics_cache_degraded_metric_value() == 1
```

- [ ] **Step 5: Verify RED**

Run: `python -m pytest services/analytics/tests -q`

Expected: FAIL before Analytics implementation exists.

- [ ] **Step 6: Verify Event-owned analytics view contract**

Do not modify `services/event/migrations/versions/0001_event_tables.py` in this task because Task 5 has already applied it. Verify that the view created in Task 4 exposes exactly the MVP fields Analytics needs: `event_id`, `user_id`, `category_id`, `category_name`, and `local_date`. Verify `pawprints_analytics_ro` can SELECT this view and cannot SELECT `events.events.description` or base Event tables directly.

- [ ] **Step 7: Add Analytics Compose and Nginx routing**

Add private `analytics` service to Compose. Do not add a Compose test-runner service for host-run pytest. Route exact and nested public Analytics paths while preserving the original URI:

```nginx
location = /api/v1/analytics { proxy_pass http://analytics:8000; }
location /api/v1/analytics/ { proxy_pass http://analytics:8000; }
```

Do not route `/internal/analytics/*` through public Nginx.

- [ ] **Step 8: Implement Analytics routes and cache**

Require explicit inclusive `start_date` and `end_date`. Frontend presets are not accepted as backend presets. Query read-only view with `WHERE user_id = :current_user_id AND local_date BETWEEN :start_date AND :end_date`. Cache user-scoped results under `analytics:v1:user:{user_id}:ver:{version}:activity-counts:{filter_hash}` with TTL.

- [ ] **Step 9: Implement internal invalidation**

`POST /internal/analytics/users/{user_id}/invalidate` requires Event internal credentials and increments `analytics:user:{user_id}:version`. Failure returns a safe error for internal callers but Event Service treats invalidation as best effort.

- [ ] **Step 10: Ensure Event analytics view exists in isolated test database**

Run with `$env:EVENT_DATABASE_URL` from Step 1 still set:

```pwsh
python -m alembic -c services/event/alembic.ini upgrade head
```

Expected: migration exits 0 in the current isolated `pawprints_test` database and `events.analytics_event_facts` exists for the Analytics tests. Do not depend on test database state left behind by an earlier task or session.

- [ ] **Step 11: Verify GREEN**

Run with `$env:EVENT_DATABASE_URL`, `$env:ANALYTICS_DATABASE_URL`, and `$env:REDIS_URL` from Step 1 still set: `python -m pytest services/analytics/tests services/event/tests packages/pawprints-common/tests -q`

Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add services/analytics compose.yaml infra/nginx/nginx.conf
git commit -m "feat: add analytics service"
```

### Task 9: Event Hard Delete Orchestration and Derived-View Verification

**Files:**
- Modify: `services/event/app/events.py`
- Modify: `services/event/app/clients.py`
- Modify: `services/event/tests/test_event_api.py`
- Modify: `services/event/tests/test_optimistic_locking.py`
- Modify: `services/event/tests/test_event_security.py`
- Modify: `tests/smoke/pawprints_smoke.py`

**Interfaces:**
- Consumes Media cleanup internal endpoint and Analytics invalidation endpoint.
- Produces version-conditional `DELETE /api/v1/events/{event_id}` behavior.

- [ ] **Step 1: Write deletion orchestration tests**

```python
def test_delete_calls_media_cleanup_before_event_delete(client, token_a, event_a, media_cleanup_spy):
    response = client.delete(f"/api/v1/events/{event_a.id}", headers={**bearer(token_a), "If-Match": '"1"'})
    assert response.status_code == 204
    assert media_cleanup_spy.called_before_event_deleted(event_a.id)

def test_media_cleanup_failure_keeps_event(client, token_a, event_a, failing_media_cleanup):
    response = client.delete(f"/api/v1/events/{event_a.id}", headers={**bearer(token_a), "If-Match": '"1"'})
    assert response.status_code >= 500
    assert get_event_row(event_a.id) is not None

def test_final_delete_is_version_conditional(client, token_a, event_a, concurrent_event_update):
    response = client.delete(f"/api/v1/events/{event_a.id}", headers={**bearer(token_a), "If-Match": '"1"'})
    assert response.status_code == 412
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest services/event/tests/test_event_api.py services/event/tests/test_optimistic_locking.py -q`

Expected: FAIL until delete orchestration is implemented.

- [ ] **Step 3: Implement media-first deletion**

Use this sequence in `services/event/app/events.py`: authenticate JWT, short DB ownership/version read, release transaction, call Media cleanup with Event internal token and request ID, open new DB transaction, execute final `DELETE ... WHERE id=:id AND user_id=:user_id AND version=:expected_version`, then best-effort Analytics invalidation.

- [ ] **Step 4: Extend smoke to verify deletion effects**

Add after create/upload/search/analytics:

```python
delete_event(session, gateway_url, auth.access_token, event["id"], event["etag"])
assert event["id"] not in [item["id"] for item in get_timeline(session, gateway_url, auth.access_token, event["local_date"])["items"]]
assert search_events(session, gateway_url, auth.access_token, keyword="Morning run")["items"] == []
assert list_media(session, gateway_url, auth.access_token, event["id"]).status_code == 404
assert analytics_count_for_category(session, gateway_url, auth.access_token, category["id"]) == 0
```

- [ ] **Step 5: Verify GREEN**

Run:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 test
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke
```

Expected: backend tests pass and smoke verifies Timeline/Search/Media/Analytics reflect hard delete.

- [ ] **Step 6: Commit**

```bash
git add services/event tests/smoke
git commit -m "feat: orchestrate event hard delete"
```

---

## Phase 5: Frontend Vertical Slice

### Task 10: React App Shell, Auth Runtime State, and API Client

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Create: `apps/web/vite.config.ts`
- Modify: `apps/web/index.html`
- Modify: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/api/client.ts`
- Create: `apps/web/src/auth/AuthProvider.tsx`
- Create: `apps/web/src/auth/LoginPage.tsx`
- Create: `apps/web/src/auth/RegisterPage.tsx`
- Create: `apps/web/src/auth/ProtectedRoute.tsx`
- Create: `apps/web/src/styles.css`
- Test: `apps/web/src/auth/AuthProvider.test.tsx`

**Interfaces:**
- Produces frontend API client `apiRequest<T>(path: string, options?: ApiOptions) -> Promise<ApiResponse<T>>`.
- Produces auth context with runtime-only `accessToken`, `user`, `login`, `register`, `logout`, and single-flight `refresh`.
- Consumes public `/api/v1/auth/*` endpoints through relative URLs.

- [ ] **Step 1: Install frontend dependencies from committed lockfile**

Update the minimal package created in Task 5 to include React Router, lucide-react, react-markdown, remark-gfm, remark-breaks, Vitest, React Testing Library, and jsdom. Then run:

```pwsh
cd apps/web
npm install
npm ci
cd ../..
```

Expected: `npm ci` exits 0 and `apps/web/package-lock.json` remains committed.

- [ ] **Step 2: Write auth client single-flight and recursion-prevention tests**

```typescript
it("shares one refresh request when several requests receive 401", async () => {
  const refreshSpy = vi.fn().mockResolvedValue(sessionResponse);
  const client = createApiClient({ refresh: refreshSpy });
  await Promise.all([
    client.request("/api/v1/events/timeline?date=2026-09-09"),
    client.request("/api/v1/categories"),
  ]);
  expect(refreshSpy).toHaveBeenCalledTimes(1);
});

it("does not recursively refresh when refresh itself fails", async () => {
  const refreshSpy = vi.fn().mockRejectedValue(new Error("session expired"));
  const client = createApiClient({ refresh: refreshSpy });
  const result = await client.request("/api/v1/events/timeline?date=2026-09-09");
  expect(result.authenticated).toBe(false);
  expect(refreshSpy).toHaveBeenCalledTimes(1);
});

it.each(["/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/logout", "/api/v1/auth/refresh"])(
  "does not trigger automatic refresh for auth session endpoint %s",
  async (path) => {
    const refreshSpy = vi.fn();
    const client = createApiClient({ refresh: refreshSpy });
    await client.request(path, { method: "POST", authMode: "session" });
    expect(refreshSpy).not.toHaveBeenCalled();
  }
);
```

- [ ] **Step 3: Verify RED**

Run: `cd apps/web; npm test -- --run src/auth/AuthProvider.test.tsx`

Expected: FAIL before app/client exist.

- [ ] **Step 4: Implement Vite app and proxy**

Configure Vite dev server:

```typescript
server: {
  proxy: {
    "/api": "http://localhost:8080"
  }
}
```

The app uses relative `/api/v1/*` URLs only.

- [ ] **Step 5: Implement auth runtime state**

Keep access token in React state/module memory only. Do not use localStorage/sessionStorage/IndexedDB. On app start, call `POST /api/v1/auth/refresh`; if it succeeds, restore user and token. The API client distinguishes protected business requests from Auth session endpoints: protected request 401 may trigger one single-flight refresh and one retry, while `/auth/refresh` never triggers refresh and login/register/logout failures never enter a refresh loop.

- [ ] **Step 6: Verify GREEN**

Run: `cd apps/web; npm test -- --run src/auth/AuthProvider.test.tsx`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web
git commit -m "feat: add web auth shell"
```

### Task 11: Timeline, Pawprint Form, Restricted Markdown, and Private Media Carousel

**Files:**
- Create: `apps/web/src/events/EventApi.ts`
- Create: `apps/web/src/events/TimelinePage.tsx`
- Create: `apps/web/src/events/EventForm.tsx`
- Create: `apps/web/src/events/EventEntry.tsx`
- Create: `apps/web/src/events/MarkdownDescription.tsx`
- Create: `apps/web/src/media/MediaApi.ts`
- Create: `apps/web/src/media/MediaCarousel.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`
- Test: `apps/web/src/events/EventForm.test.tsx`
- Test: `apps/web/src/events/TimelinePage.test.tsx`
- Test: `apps/web/src/media/MediaCarousel.test.tsx`

**Interfaces:**
- Produces `/timeline` route.
- Consumes category/event/media APIs.
- Produces `fetchMediaObjectUrl(mediaId: string) -> Promise<string>` and `revokeMediaObjectUrl(url: string) -> void`.
- Produces EventForm behavior that creates the Event first, uploads selected images afterward through `uploadEventMedia(eventId: string, files: File[])`, preserves the Event if image upload fails, and exposes manual retry for failed images.

- [ ] **Step 1: Write Timeline, Blob lifecycle, Markdown allowlist, and image upload tests**

Import `within` from `@testing-library/react` for the Markdown subtree assertions.

```typescript
it("renders timeline entries in chronological order", async () => {
  render(<TimelinePage />);
  expect(await screen.findAllByRole("article")).toHaveTextContentSequence(["08:00 Morning run", "18:00 Dinner"]);
});

it("fetches private media as blobs and revokes object URLs on unmount", async () => {
  const revokeSpy = vi.spyOn(URL, "revokeObjectURL");
  const { unmount } = render(<MediaCarousel media={[{ id: "m1", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" }]} />);
  await screen.findByRole("img");
  unmount();
  expect(revokeSpy).toHaveBeenCalled();
});

it("does not render unsupported markdown elements or raw html", () => {
  const { container } = render(<MarkdownDescription source={"# Heading\n[link](https://example.com)\n![alt](https://example.com/a.png)\n<div>raw</div>\n**bold**"} />);
  const markdown = within(container).getByTestId("markdown-description");
  expect(within(markdown).queryByRole("heading")).toBeNull();
  expect(within(markdown).queryByRole("link")).toBeNull();
  expect(within(markdown).queryByAltText("alt")).toBeNull();
  expect(markdown.querySelector("div")).toBeNull();
  expect(within(markdown).getByText("bold").tagName.toLowerCase()).toBe("strong");
});

it("creates the event before uploading selected images and preserves it when upload fails", async () => {
  const createEvent = vi.fn().mockResolvedValue({ id: "event-1", etag: "\"1\"", local_date: "2026-09-09" });
  const uploadEventMedia = vi.fn()
    .mockRejectedValueOnce(new Error("upload failed"))
    .mockResolvedValueOnce([{ id: "media-1", display_order: 1, mime_type: "image/png", file_size: 100, created_at: "2026-09-09T00:00:00Z" }]);

  render(<EventForm createEvent={createEvent} uploadEventMedia={uploadEventMedia} />);
  await userEvent.upload(screen.getByLabelText("Images"), [new File(["png"], "paw.png", { type: "image/png" })]);
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(createEvent).toHaveBeenCalledTimes(1);
  expect(uploadEventMedia).toHaveBeenCalledWith("event-1", expect.any(Array));
  expect(await screen.findByText("Image upload failed")).toBeInTheDocument();
  expect(screen.getByText("Pawprint saved")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Retry image upload" }));
  expect(await screen.findByRole("img")).toBeInTheDocument();
});
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/web; npm test -- --run src/events/EventForm.test.tsx src/events/TimelinePage.test.tsx src/media/MediaCarousel.test.tsx`

Expected: FAIL before components exist.

- [ ] **Step 3: Implement Timeline default and navigation**

Default date is browser today. Include previous day, today, next day, date input, and prominent New Pawprint action. Render entries vertical and chronological.

- [ ] **Step 4: Implement Event form and post-create image upload**

Required fields: title max 120, category_id, intended local datetime, timezone. Optional: description max 10,000, mood enum, location_name, latitude/longitude. Support quick category creation as explicit category API call before Event creation. Add optional 0-5 image file selection with basic client count/type feedback for JPEG, PNG, and WebP where inexpensive; backend validation remains authoritative.

On submit, create the Event first. After receiving `event_id`, upload selected images through `uploadEventMedia(eventId, files)`. Never roll back or delete a successfully created Event because a later image upload fails. If one or more image uploads fail, keep the Event visible, show failed image state, and provide a manual "Retry image upload" action for the selected files that did not upload. After successful uploads, render returned Media through the private authenticated Blob URL carousel flow.

- [ ] **Step 5: Implement restricted Markdown**

Use `react-markdown`, `remark-gfm`, and `remark-breaks`. Disable raw HTML with `skipHtml={true}` and do not use `rehype-raw`. Enforce the approved subset with `allowedElements={["p","strong","em","del","ul","ol","li","br"]}`; do not rely on the `components` mapping as the security/scope allowlist. Render the Markdown subtree with `data-testid="markdown-description"` for focused tests. Links, headings, Markdown images, tables, code blocks, task lists, and raw HTML must not render as active elements. Add toolbar buttons that wrap selected text with `**`, `*`, and `~~`.

- [ ] **Step 6: Implement private Media carousel**

Fetch `/api/v1/media/{media_id}` with `Authorization: Bearer <accessToken>`, convert `Blob` to `URL.createObjectURL`, render `<img src={objectUrl}>`, and revoke URLs on media change/unmount. Do not place Bearer tokens in image URLs.

- [ ] **Step 7: Implement edit/delete UX**

Store latest ETag from GET/create/update. Send `If-Match` on PATCH and DELETE. On 412, fetch current version and show manual review state. Do not optimistically delete before server 204.

- [ ] **Step 8: Verify GREEN**

Run: `cd apps/web; npm test -- --run src/events/EventForm.test.tsx src/events/TimelinePage.test.tsx src/media/MediaCarousel.test.tsx`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add apps/web
git commit -m "feat: add timeline and media carousel"
```

### Task 12: Search and User Analytics UI

**Files:**
- Create: `apps/web/src/search/SearchPage.tsx`
- Create: `apps/web/src/search/SearchApi.ts`
- Create: `apps/web/src/analytics/AnalyticsPage.tsx`
- Create: `apps/web/src/analytics/AnalyticsApi.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`
- Test: `apps/web/src/analytics/AnalyticsPage.test.tsx`

**Interfaces:**
- Produces `/search` and `/analytics` routes.
- Consumes explicit Analytics date range API with frontend-resolved presets.

- [ ] **Step 1: Write frontend preset date test**

```typescript
it("resolves current month preset before calling analytics API", () => {
  vi.setSystemTime(new Date("2026-09-09T10:00:00+08:00"));
  expect(resolveAnalyticsPreset("current-month")).toEqual({ start_date: "2026-09-01", end_date: "2026-09-30" });
});
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/web; npm test -- --run src/analytics/AnalyticsPage.test.tsx`

Expected: FAIL before Analytics page exists.

- [ ] **Step 3: Implement Search page**

Filters: keyword, date/date range, category, mood, location. Use `/api/v1/events/search` and expandable `EventEntry` presentation where practical.

- [ ] **Step 4: Implement Analytics page**

Resolve current month and last 30 days in the browser into explicit inclusive `start_date`/`end_date`. Render category counts and simple bars; weekly/monthly grouping controls call API with `grouping=week` or `grouping=month`.

- [ ] **Step 5: Verify GREEN**

Run: `cd apps/web; npm test -- --run src/analytics/AnalyticsPage.test.tsx`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web
git commit -m "feat: add search and analytics views"
```

---

## Phase 6: Observability and Demo-Ready Compose

### Task 13: Service Logs, Metrics, Health, Readiness, Prometheus, and Grafana

**Files:**
- Modify: `packages/pawprints-common/pawprints_common/request_context.py`
- Modify: `packages/pawprints-common/pyproject.toml`
- Create: `packages/pawprints-common/pawprints_common/observability.py`
- Modify: `infra/nginx/nginx.conf`
- Modify: `services/auth/app/main.py`
- Modify: `services/event/app/main.py`
- Modify: `services/media/app/main.py`
- Modify: `services/analytics/app/main.py`
- Create: `infra/prometheus/prometheus.yml`
- Create: `infra/grafana/provisioning/datasources/prometheus.yml`
- Create: `infra/grafana/provisioning/dashboards/dashboards.yml`
- Create: `infra/grafana/dashboards/pawprints-service-overview.json`
- Modify: `compose.yaml`
- Test: `packages/pawprints-common/tests/test_observability.py`

**Interfaces:**
- Produces common middleware `install_request_context_and_metrics(app: FastAPI, service_name: str) -> None`.
- Produces `/healthz`, `/readyz`, and internal `/metrics` in each FastAPI service.

- [ ] **Step 1: Write observability tests**

```python
def test_request_log_uses_route_template_and_omits_private_values(caplog, client):
    client.get("/api/v1/events/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", headers=bearer_token())
    record = parse_json_log(caplog.records[-1].message)
    assert record["route"] == "/api/v1/events/{event_id}"
    assert "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" not in record.values()

def test_metrics_route_labels_are_normalized(client):
    client.get("/api/v1/events/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", headers=bearer_token())
    metrics = client.get("/metrics").text
    assert 'route="/api/v1/events/{event_id}"' in metrics
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest packages/pawprints-common/tests/test_observability.py -q`

Expected: FAIL before observability helpers exist.

- [ ] **Step 3: Finalize Nginx request ID ownership**

In `infra/nginx/nginx.conf`, public requests use Nginx `$request_id` as the authoritative request ID. Return it with `add_header X-Request-Id $request_id always;` and forward it with `proxy_set_header X-Request-Id $request_id;`. Do not forward arbitrary client-supplied `X-Request-Id` as authoritative. Services propagate the received Nginx request ID unchanged on service-to-service calls.

- [ ] **Step 4: Add common Prometheus dependency**

Modify `packages/pawprints-common/pyproject.toml` to add runtime dependency `prometheus-client`. Then run:

```pwsh
python -m pip install -e "packages/pawprints-common[dev]"
```

Expected: dependency installation exits 0 before implementing or verifying metrics behavior.

- [ ] **Step 5: Implement common observability**

Add structured logs with request_id, service, level, method, route template, status, latency, and safe error/event codes. Add Prometheus RED metrics with low-cardinality labels. Do not label user_id, event_id, filenames, diary/search content, raw URLs, locations, storage keys, or tokens.

- [ ] **Step 6: Add service health/readiness**

`/healthz` returns process liveness. `/readyz` checks required dependencies. Analytics readiness requires PostgreSQL/read-view availability; Redis unavailability reports degraded cache state through logs/metrics but does not fail readiness when DB fallback works.

- [ ] **Step 7: Provision Prometheus and Grafana**

Prometheus scrapes `auth:8000/metrics`, `event:8000/metrics`, `media:8000/metrics`, and `analytics:8000/metrics` on the internal Compose network. Grafana loads Prometheus datasource and `Pawprints Service Overview` dashboard automatically.

- [ ] **Step 8: Verify observability stack**

Run:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 up
curl http://localhost:9090/-/ready
curl http://localhost:3000/api/health
```

Expected: Prometheus ready and Grafana health endpoint returns OK. Service metrics are visible in Prometheus targets.

- [ ] **Step 9: Commit**

```bash
git add packages/pawprints-common services infra/nginx/nginx.conf infra/prometheus infra/grafana compose.yaml
git commit -m "feat: add Pawprints observability baseline"
```

---

## Phase 7: Final Test, Smoke, Seed, and Documentation Hardening

### Task 14: Mandatory Security and Concurrency Regression Sweep

**Files:**
- Modify: `services/auth/tests/test_refresh_rotation.py`
- Modify: `services/event/tests/test_event_security.py`
- Modify: `services/event/tests/test_optimistic_locking.py`
- Modify: `services/media/tests/test_media_security.py`
- Modify: `services/analytics/tests/test_security.py`
- Modify: `scripts/dev.ps1`

**Interfaces:**
- Produces a `dev.ps1 test` command that runs all mandatory backend and common tests.

- [ ] **Step 1: Ensure P0 test list exists exactly**

Tests must cover:

```text
User B cannot read/update/delete User A's Events.
User B cannot create an Event using User A's category_id.
User B cannot PATCH one of User B's Events to reference User A's category_id.
User B cannot modify User A's Categories.
User B cannot upload Media to User A's Event.
User B cannot list/retrieve/delete User A's Media.
Analytics never aggregates another user's data.
Redis cached analytics cannot leak across users.
Authorization errors do not expose foreign resource/version details.
Stale If-Match update/delete returns 412 for authenticated owners.
Concurrent refresh allows at most one successful rotation.
```

- [ ] **Step 2: Run mandatory backend tests**

Run:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 test
```

Expected: all backend/common tests pass. If any test fails, use `superpowers:systematic-debugging` during execution before fixing.

- [ ] **Step 3: Commit**

```bash
git add services packages scripts/dev.ps1
git commit -m "test: enforce Pawprints security regressions"
```

### Task 15: Full Compose Smoke, Seed, and README Demo Workflow

**Files:**
- Modify: `tests/smoke/pawprints_smoke.py`
- Create: `demo/seed.py`
- Create: `demo/assets/sample.png`
- Modify: `scripts/dev.ps1`
- Modify: `README.md`

**Interfaces:**
- Produces mandatory full-stack smoke path through Nginx.
- Produces optional API-driven seed command that is disabled by default.

- [ ] **Step 1: Expand smoke to the approved vertical slice**

`tests/smoke/pawprints_smoke.py` must execute:

```text
GET / returns the Pawprints React frontend/index through Nginx
register
login session established
create category
create Pawprint
upload images
Daily Timeline contains Pawprint in chronological order
expanded data can fetch diary and media
PATCH with If-Match edits Pawprint
Search finds edited Pawprint
Analytics includes category count
DELETE with If-Match hard-deletes Pawprint
Timeline, Search, Media, and Analytics reflect deletion
```

- [ ] **Step 2: Verify smoke RED against incomplete paths**

Run: `pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke`

Expected: if any vertical-slice requirement is missing, smoke fails with the missing behavior named.

- [ ] **Step 3: Implement API-driven seed**

`demo/seed.py` uses public Nginx APIs only. It registers or reuses one demo user, logs in, creates 4-5 categories, creates 8-12 synthetic events across recent days/weeks using `Asia/Taipei`, uploads safe sample media when available, and optionally calls Search/Analytics to generate demo traffic. Credentials come from ignored local env values.

- [ ] **Step 4: Wire `dev.ps1 seed`, `start`, and `demo`**

Put the `seed` service under `profiles: ["jobs"]`. `seed` runs only when explicitly called. `start` orchestrates setup, `docker compose up --build -d --wait postgres redis`, explicit migrations, `docker compose up --build -d --wait auth event media analytics nginx prometheus grafana`, and smoke. This rebuilds the Nginx React artifact before final smoke. `demo` runs `start` then `seed`. Any health/readiness timeout throws and preserves a nonzero exit code. Neither command deletes volumes.

- [ ] **Step 5: Verify full demo path**

Run:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 down
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 start
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 seed
```

Expected: infrastructure healthchecks pass before migrations begin, application/monitoring healthchecks pass before smoke begins, smoke passes through Nginx, seed runs through public APIs, Prometheus and Grafana are available, and existing DB/media volumes survive normal `down`.

- [ ] **Step 6: Update README**

Document:

```text
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 setup
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 up
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 migrate
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 seed
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 down
```

Also document the underlying `docker compose` commands for transparency, Nginx as the public boundary, Prometheus/Grafana local URLs, and that destructive reset is explicitly named and separate from `down`.

Document PowerShell 7 as a prerequisite and use only `pwsh` examples. Do not include legacy shell command examples.

- [ ] **Step 7: Commit**

```bash
git add tests/smoke demo scripts/dev.ps1 README.md
git commit -m "chore: add full Pawprints demo workflow"
```

### Task 16: Final Whole-System Verification Gate

**Files:**
- Modify: `README.md` only if verification reveals documentation mismatch.

**Interfaces:**
- Produces final evidence that the approved MVP implementation is ready for review.

- [ ] **Step 1: Run backend/common test suite**

Run: `pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 test`

Expected: PASS with all mandatory backend/common/security tests.

- [ ] **Step 2: Run frontend tests that exist**

Run: `cd apps/web; npm test -- --run`

Expected: PASS for implemented frontend tests. If no frontend tests were added beyond optional scope, document that only backend and smoke are mandatory.

- [ ] **Step 3: Run full stack smoke**

Run:

```pwsh
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 down
pwsh -ExecutionPolicy Bypass -File scripts/dev.ps1 start
```

Expected: setup, explicit migrations, readiness, and smoke complete successfully through Nginx.

- [ ] **Step 4: Verify observability demo endpoints**

Run:

```pwsh
curl http://localhost:9090/-/ready
curl http://localhost:3000/api/health
```

Expected: Prometheus ready and Grafana health OK.

- [ ] **Step 5: Verify no future/non-goal feature implementation slipped in**

Run:

```pwsh
rg -n "kubernetes|k8s|service mesh|opentelemetry|otel|service-mesh|presigned|oauth|mfa|rbac|category delete|category_delete|activity tag|activity_tag|postgis|loki|alertmanager" compose.yaml services apps packages infra
rg -n "\"(boto3|aioboto3|opentelemetry|prometheus-node-exporter|loki|@react-oauth|@auth0|keycloak|leaflet|mapbox|postgis)\"" services/*/pyproject.toml apps/web/package.json
Get-ChildItem -Recurse -Directory services,apps,packages,infra | Where-Object { $_.Name -match "oauth|rbac|admin|category-delete|activity-tags|postgis|thumbnail|presigned|otel|opentelemetry|loki|alertmanager" }
```

Expected: review/classify any matches. Legitimate matches such as `POSTGRES_ADMIN_USER`, unsupported-media rejection tests, documentation, comments naming explicit non-goals, and safe validation constants are acceptable. Unexpected dependencies, infrastructure services, directories, modules, routes, or UI surfaces for future/non-goal features must be removed before approval.

- [ ] **Step 6: Commit final verification/doc adjustment if needed**

```bash
git add README.md
git commit -m "docs: align Pawprints verification notes"
```

Only run this commit if `README.md` changed.

---

## Implementation Priority Notes

Build in this order because it gets the vertical slice working early:

1. Shared auth primitives and Auth Service.
2. Event Service category/event/timeline/search with ownership and optimistic locking.
3. Nginx/Compose partial smoke through Auth + Event.
4. Media Service and private carousel-safe retrieval.
5. Analytics read-only view/cache/invalidation.
6. Event hard delete with Media cleanup and Analytics invalidation.
7. React UI for Timeline-first vertical slice.
8. Observability, seed, README, and final verification.

When a task involves behavior suitable for tests, use RED -> verify failing test -> GREEN -> verify -> REFACTOR. For infrastructure-only tasks, the verification command is the test.

Do not start implementation until this plan is approved.
