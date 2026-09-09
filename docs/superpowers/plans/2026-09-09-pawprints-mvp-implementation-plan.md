# Pawprints MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved Pawprints one-day MVP vertical slice end-to-end, then deepen the mandatory security, concurrency, observability, and smoke verification.

**Architecture:** Pawprints is a split monorepo with React/Vite frontend, Nginx public gateway, and four synchronous FastAPI services: Auth, Event, Media, and Analytics. Services communicate over explicit HTTP APIs on the private Docker Compose network, own their schemas/migrations, validate JWTs locally with shared RS256 verification code, and preserve object-level ownership.

**Tech Stack:** React, TypeScript, Vite, React Router, plain CSS, lucide-react, Python, FastAPI, Pydantic, SQLAlchemy, Alembic, httpx.Client, PostgreSQL, Redis, Pillow, pytest, Docker Compose, Nginx, Prometheus, Grafana, PowerShell.

**Spec:** `docs/superpowers/specs/2026-09-09-pawprints-mvp-design.md`

## Global Constraints

- Do not implement Future / MVP Non-Goal items from the spec.
- Do not create a worktree for this implementation unless the user later asks for one.
- Keep backend services deployable as separate containers under `services/auth`, `services/event`, `services/media`, and `services/analytics`.
- Keep `packages/pawprints-common` limited to JWT verification, internal service auth, authenticated identity, request/error helpers, and focused tests.
- Use ordinary FastAPI `def` endpoints, synchronous SQLAlchemy Sessions, synchronous Alembic, reusable synchronous `httpx.Client` instances, and blocking Pillow image processing.
- Use RS256 access JWTs only. Auth issues with private key; Event, Media, and Analytics verify with public key.
- Use explicit JWT config consistently: `JWT_ISSUER=pawprints-auth`, `JWT_AUDIENCE=pawprints-api`, `ACCESS_TOKEN_TTL_MINUTES=15`.
- Use opaque refresh tokens, SHA-256 token hashes, Argon2id passwords, 7-day absolute refresh sessions, and refresh rotation on every successful refresh.
- Browser stores access JWT only in runtime memory. Never persist it in localStorage, sessionStorage, IndexedDB, URLs, or query strings.
- Refresh token is delivered only through an HttpOnly cookie scoped to `/api/v1/auth`, with Secure required in production and configurable for localhost.
- Nginx is the public API boundary. Browser API calls use relative `/api/v1/*` URLs. Backend service ports stay private to Compose.
- Private `/internal/*` service endpoints are not routed through Nginx and require per-caller static internal tokens plus endpoint authorization.
- Use one local PostgreSQL database with `auth`, `events`, and `media` schemas, least-privilege roles, and explicit per-service Alembic migration jobs.
- Analytics reads only approved Event-owned analytics views through a read-only database role.
- Redis is used only as a degradable, user-scoped Analytics cache.
- Local media storage uses a `LocalFileStorage` adapter backed by a persistent Docker named volume or ignored host data directory; normal `down` does not delete DB or media data.
- All externally visible IDs are server-generated UUIDv4 values stored as PostgreSQL `uuid`.
- Mutable Events and Categories use integer `version` values and quoted integer ETags, for example `ETag: "1"` and `If-Match: "1"`.
- Event creation/update must verify any supplied `category_id` belongs to the authenticated user.
- Media public JSON must never expose `storage_key` or filesystem paths.
- Prometheus/Grafana are part of MVP; metrics labels must be low-cardinality and privacy-safe.
- Mandatory P0 security tests must be implemented early enough to guide service behavior, not as a final cosmetic pass.

---

## File Structure Map

Create or modify these repository areas as tasks make them real:

- `compose.yaml`: full local stack, migration jobs, private services, Nginx, PostgreSQL, Redis, Prometheus, Grafana, persistent media volume.
- `.env.example`: committed safe configuration template with placeholders and non-secret defaults.
- `.gitignore`: ignored `.env`, generated keys, local secrets, local data directory if used, Python/Node build artifacts.
- `README.md`: transparent PowerShell and Docker Compose workflow.
- `scripts/dev.ps1`: `setup`, `migrate`, `up`, `test`, `smoke`, `seed`, `down`, optional `start`/`demo`, explicit destructive reset only if added.
- `infra/postgres/init/001-bootstrap.sql`: database schemas, roles, grants, read-only Analytics view grants.
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
- `apps/web/package.json`, `apps/web/vite.config.ts`, `apps/web/src/*`, `apps/web/Dockerfile`, `apps/web/nginx.conf`
- `tests/smoke/pawprints_smoke.py`: whole-stack smoke through Nginx.
- `demo/seed.py` and optional `demo/assets/*`: API-driven seed data only.

---

## Phase 1: Platform Spine and Security Primitives

### Task 1: Monorepo Skeleton, Config, and Dev Script Surface

**Files:**
- Create: `compose.yaml`
- Create: `.env.example`
- Modify: `.gitignore`
- Create: `README.md`
- Create: `scripts/dev.ps1`
- Create: `infra/postgres/init/001-bootstrap.sql`

**Interfaces:**
- Produces: directory layout, config variable names, PowerShell task entrypoint, PostgreSQL schemas/roles.
- Later tasks consume: `JWT_ISSUER=pawprints-auth`, `JWT_AUDIENCE=pawprints-api`, per-service DB URLs, per-caller internal token env vars, `MEDIA_STORAGE_ROOT=/var/lib/pawprints/media`.

- [ ] **Step 1: Create skeleton directories**

Create only directories used by this task and the next immediate tasks:

```powershell
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

AUTH_DATABASE_URL=postgresql+psycopg://pawprints_auth_rw:CHANGE_ME@postgres:5432/pawprints
EVENT_DATABASE_URL=postgresql+psycopg://pawprints_event_rw:CHANGE_ME@postgres:5432/pawprints
MEDIA_DATABASE_URL=postgresql+psycopg://pawprints_media_rw:CHANGE_ME@postgres:5432/pawprints
ANALYTICS_DATABASE_URL=postgresql+psycopg://pawprints_analytics_ro:CHANGE_ME@postgres:5432/pawprints

REDIS_URL=redis://redis:6379/0
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

- [ ] **Step 4: Add PostgreSQL bootstrap**

`infra/postgres/init/001-bootstrap.sql` creates schemas and least-privilege roles using variables supplied by Compose initialization. Keep grants narrow:

```sql
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS events;
CREATE SCHEMA IF NOT EXISTS media;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE ROLE pawprints_auth_rw LOGIN PASSWORD :'AUTH_DB_PASSWORD';
CREATE ROLE pawprints_event_rw LOGIN PASSWORD :'EVENT_DB_PASSWORD';
CREATE ROLE pawprints_media_rw LOGIN PASSWORD :'MEDIA_DB_PASSWORD';
CREATE ROLE pawprints_analytics_ro LOGIN PASSWORD :'ANALYTICS_DB_PASSWORD';

GRANT USAGE, CREATE ON SCHEMA auth TO pawprints_auth_rw;
GRANT USAGE, CREATE ON SCHEMA events TO pawprints_event_rw;
GRANT USAGE, CREATE ON SCHEMA media TO pawprints_media_rw;
GRANT USAGE ON SCHEMA events TO pawprints_analytics_ro;
```

If PostgreSQL init variable substitution is not available with plain `.sql`, replace this with a `.sh` wrapper in the same directory that calls `psql -v AUTH_DB_PASSWORD=...` and keeps the same SQL body.

- [ ] **Step 5: Add initial `scripts/dev.ps1` command parser**

Create a PowerShell script with explicit cases:

```powershell
param(
  [Parameter(Mandatory=$true)]
  [ValidateSet("setup","migrate","up","test","smoke","seed","down","start","demo","reset-data")]
  [string]$Command
)

$ErrorActionPreference = "Stop"

switch ($Command) {
  "setup" { Write-Host "Setting up local config and secrets"; exit 0 }
  "migrate" { docker compose run --rm auth-migrate; docker compose run --rm event-migrate; docker compose run --rm media-migrate }
  "up" { docker compose up -d }
  "test" { docker compose run --rm auth-test; docker compose run --rm event-test; docker compose run --rm media-test; docker compose run --rm analytics-test }
  "smoke" { docker compose run --rm smoke }
  "seed" { docker compose run --rm seed }
  "down" { docker compose down }
  "start" { & $PSCommandPath setup; docker compose up -d postgres redis; & $PSCommandPath migrate; & $PSCommandPath up; & $PSCommandPath smoke }
  "demo" { & $PSCommandPath start; & $PSCommandPath seed }
  "reset-data" {
    throw "Destructive reset is intentionally not implemented until explicitly requested during implementation."
  }
}
```

- [ ] **Step 6: Verify shell surface**

Run: `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 setup`

Expected: exits 0 and does not create seed data.

- [ ] **Step 7: Commit**

```bash
git add .gitignore .env.example README.md compose.yaml scripts/dev.ps1 infra/postgres/init/001-bootstrap.sql
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

- [ ] **Step 1: Write failing JWT tests**

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

- [ ] **Step 2: Verify RED**

Run: `python -m pytest packages/pawprints-common/tests/test_jwt.py -q`

Expected: FAIL because `pawprints_common.jwt` does not exist.

- [ ] **Step 3: Implement JWT verification**

Use `pyjwt[crypto]` or `python-jose[cryptography]`; keep algorithm fixed to `RS256`. Validate `iss`, `aud`, `exp`, and UUID-shaped `sub`. Return:

```python
@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
```

- [ ] **Step 4: Write and verify internal auth RED**

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

- [ ] **Step 5: Implement internal auth and error envelope helpers**

Implement `hmac.compare_digest`, safe exceptions, and `error_response`. `error_response` always emits:

```json
{"error":{"code":"validation_failed","message":"Some fields are invalid.","request_id":"req-123"}}
```

- [ ] **Step 6: Verify GREEN**

Run: `python -m pytest packages/pawprints-common/tests -q`

Expected: PASS.

- [ ] **Step 7: Commit**

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
- Consumes common JWT config values `pawprints-auth` and `pawprints-api`.

- [ ] **Step 1: Write password policy tests**

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

Run: `python -m pytest services/auth/tests/test_passwords.py -q`

Expected: FAIL before `passwords.py` exists.

- [ ] **Step 2: Implement Argon2id password handling**

Use `pwdlib.PasswordHash.recommended()` or equivalent Argon2id library API. Enforce exact policy: min 12, max 128, reject empty/all-whitespace, no composition rules, no trimming.

- [ ] **Step 3: Write Auth API tests**

Cover register/login/me/no-store/generic invalid credentials:

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
```

- [ ] **Step 4: Write refresh rotation and concurrency tests**

```python
def test_refresh_rotates_and_old_refresh_token_is_rejected(client):
    login = register_and_capture_refresh_cookie(client)
    first = client.post("/api/v1/auth/refresh", headers={"Origin": "http://localhost"}, cookies=login.cookies)
    second = client.post("/api/v1/auth/refresh", headers={"Origin": "http://localhost"}, cookies=login.cookies)
    assert first.status_code == 200
    assert second.status_code == 401

def test_concurrent_refresh_allows_at_most_one_success(auth_db_session, refresh_token_value):
    results = run_two_refresh_transactions(refresh_token_value)
    assert sum(result.status_code == 200 for result in results) == 1
```

- [ ] **Step 5: Verify RED**

Run: `python -m pytest services/auth/tests -q`

Expected: FAIL for missing endpoints/models.

- [ ] **Step 6: Implement Auth models, migration, routes, token issuance**

Use SQLAlchemy models for `auth.users` and `auth.refresh_tokens`. Hash refresh token with `hashlib.sha256(token.encode("utf-8")).hexdigest()`. Rotate with a transaction that locks the presented refresh row, sets `revoked_at`, inserts replacement with the same `expires_at`, and stores `replaced_by_token_id`.

- [ ] **Step 7: Verify GREEN**

Run: `python -m pytest services/auth/tests packages/pawprints-common/tests -q`

Expected: PASS.

- [ ] **Step 8: Commit**

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

- [ ] **Step 1: Write time and validation tests**

```python
def test_local_datetime_timezone_derives_utc_and_local_date():
    result = derive_event_time("2026-09-09T23:30:00", "Asia/Taipei")
    assert result.local_date.isoformat() == "2026-09-09"
    assert result.occurred_at.tzinfo is not None

def test_invalid_timezone_rejected():
    with pytest.raises(EventValidationError):
        derive_event_time("2026-09-09T12:00:00", "Not/AZone")
```

Run: `python -m pytest services/event/tests/test_time_semantics.py -q`

Expected: FAIL before implementation.

- [ ] **Step 2: Implement time semantics**

Use Python `zoneinfo.ZoneInfo`. Accept local datetime input without trusting client-supplied `local_date`. Return canonical UTC `occurred_at`, validated `timezone`, and derived `local_date`.

- [ ] **Step 3: Write category tests**

Cover list/create/rename, normalized duplicate prevention, quoted ETag, stale `If-Match`, and cross-user rename returning 404.

```python
def test_category_duplicate_is_case_insensitive_per_user(client, user_token):
    create_category(client, user_token, "Running")
    response = create_category(client, user_token, " running ")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "category_name_exists"
```

- [ ] **Step 4: Write Event ownership and foreign category tests**

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

- [ ] **Step 5: Write optimistic locking tests**

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

- [ ] **Step 6: Write Search and Timeline tests**

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

- [ ] **Step 7: Verify RED**

Run: `python -m pytest services/event/tests -q`

Expected: FAIL for missing Event service implementation.

- [ ] **Step 8: Implement Event models, migrations, routes, analytics view**

Implement `events.categories`, `events.events`, and an Event-owned analytics view such as `events.analytics_event_facts`. Register `/events/timeline` and `/events/search` before `/events/{event_id}`. Use atomic `UPDATE ... WHERE id = :id AND user_id = :user_id AND version = :expected_version RETURNING ...` semantics through SQLAlchemy.

- [ ] **Step 9: Implement internal ownership check and Analytics invalidation client**

`GET /internal/events/{event_id}/ownership` requires Media internal credentials plus forwarded Bearer JWT. Event Service validates both, checks ownership, and returns 200 for owned or 404 for missing/foreign. The Analytics invalidation client uses reusable `httpx.Client` with request ID and Event internal token; failures are logged without rolling back Event mutations.

- [ ] **Step 10: Verify GREEN**

Run: `python -m pytest services/event/tests packages/pawprints-common/tests -q`

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add services/event packages/pawprints-common
git commit -m "feat: add event service core"
```

### Task 5: Compose, Nginx, and Partial Vertical Slice Smoke for Auth + Event

**Files:**
- Modify: `compose.yaml`
- Create: `infra/nginx/nginx.conf`
- Modify: `scripts/dev.ps1`
- Create: `tests/smoke/pawprints_smoke.py`
- Modify: `README.md`

**Interfaces:**
- Produces Nginx public routes for `/api/v1/auth/*`, `/api/v1/events/*`, and `/api/v1/categories/*`.
- Produces smoke helper functions `register_user`, `login_user`, `create_category`, `create_event`, `get_timeline`.

- [ ] **Step 1: Add Compose services and migration jobs**

Define private `auth`, `event`, `postgres`, and `nginx` services plus `auth-migrate`, `event-migrate`, `auth-test`, `event-test`, and `smoke`. Do not expose `auth` or `event` ports to the host. Expose only Nginx.

- [ ] **Step 2: Configure Nginx routing**

Route:

```nginx
location /api/v1/auth/ { proxy_pass http://auth:8000/api/v1/auth/; }
location /api/v1/categories/ { proxy_pass http://event:8000/api/v1/categories/; }
location /api/v1/events/ { proxy_pass http://event:8000/api/v1/events/; }
```

Forward `Authorization`, `Cookie`, `Set-Cookie`, and `X-Request-Id`. Strip `X-User-Id`, `X-Pawprints-Internal-Service`, and `X-Pawprints-Internal-Token` from public requests.

- [ ] **Step 3: Write partial smoke test**

`tests/smoke/pawprints_smoke.py`:

```python
def test_auth_event_timeline_smoke(gateway_url):
    session = requests.Session()
    auth = register_user(session, gateway_url, unique_email(), "correct horse battery")
    category = create_category(session, gateway_url, auth.access_token, "Running")
    event = create_event(session, gateway_url, auth.access_token, category["id"], title="Morning run")
    timeline = get_timeline(session, gateway_url, auth.access_token, event["local_date"])
    assert [item["id"] for item in timeline["items"]] == [event["id"]]
```

- [ ] **Step 4: Verify RED**

Run: `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke`

Expected: FAIL before Compose/Nginx stack is fully wired.

- [ ] **Step 5: Wire `dev.ps1 migrate`, `up`, `smoke`, and `down`**

`migrate` runs only explicit migration jobs and stops on failure. `down` runs `docker compose down` and does not remove volumes.

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 setup
docker compose up -d postgres redis
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 migrate
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 up
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke
```

Expected: smoke test passes through Nginx and no backend service port is exposed to the browser/host.

- [ ] **Step 7: Commit**

```bash
git add compose.yaml infra/nginx/nginx.conf scripts/dev.ps1 tests/smoke README.md
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

- [ ] **Step 1: Write image validation tests**

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

- [ ] **Step 2: Verify RED**

Run: `python -m pytest services/media/tests/test_image_processing.py -q`

Expected: FAIL before image processing exists.

- [ ] **Step 3: Implement Pillow normalization**

Use `Image.open`, `Image.verify` or full decode, `ImageOps.exif_transpose`, `Image.n_frames` for animation rejection, `Image.MAX_IMAGE_PIXELS` left enabled, explicit pixel count check, and re-encode JPEG/PNG/WebP to metadata-stripped bytes.

- [ ] **Step 4: Write media count/order/security tests**

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

- [ ] **Step 5: Write compensation tests**

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
```

- [ ] **Step 6: Verify RED**

Run: `python -m pytest services/media/tests -q`

Expected: FAIL before Media routes/storage/DB exist.

- [ ] **Step 7: Implement Media metadata migration and LocalFileStorage**

Create `media.event_media` with UUID id, event_id, storage_key, mime_type, file_size, display_order, created_at, and unique `(event_id, display_order)`. Store files under `MEDIA_STORAGE_ROOT` using generated keys. Use a persistent Compose volume mounted at `/var/lib/pawprints/media`.

- [ ] **Step 8: Implement upload transaction and cleanup**

Decode/normalize first into temporary in-memory or temporary file objects. Enter a short DB transaction, acquire per-event transaction advisory lock, recount media, reject `existing + incoming > 5`, assign display_order values, write files, insert metadata, commit. On any rejection or metadata failure after writing files, best-effort delete newly written files before returning a safe error.

- [ ] **Step 9: Implement private retrieval and deletion**

Every list/retrieve/delete path verifies Event ownership through Event Service. Stream bytes only after authz. Deletion hard-deletes metadata and file and never renumbers display order.

- [ ] **Step 10: Implement idempotent internal cleanup**

`POST /internal/media/events/{event_id}/cleanup` requires Event internal credentials, deletes all files and metadata for the Event, and returns success even when no media remain.

- [ ] **Step 11: Verify GREEN**

Run: `python -m pytest services/media/tests services/event/tests/test_event_security.py packages/pawprints-common/tests -q`

Expected: PASS.

- [ ] **Step 12: Commit**

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

- [ ] **Step 1: Add Media service, migration, and test jobs to Compose**

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

- [ ] **Step 2: Add Nginx Media routing and body limit**

Configure `/api/v1/media/` with body size above 25 MB and JSON 413 response. Continue stripping internal headers.

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

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 migrate
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke
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
- Modify: `services/event/migrations/versions/0001_event_tables.py`
- Test: `services/analytics/tests/test_activity_counts.py`
- Test: `services/analytics/tests/test_cache.py`
- Test: `services/analytics/tests/test_security.py`
- Test: `services/analytics/tests/test_redis_degraded.py`

**Interfaces:**
- Produces public endpoint `GET /api/v1/analytics/activity-counts?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&grouping=none|week|month`.
- Produces internal endpoint `POST /internal/analytics/users/{user_id}/invalidate`.
- Consumes read-only `events.analytics_event_facts` view.
- Produces cache helpers `cache_key(user_id: UUID, version: int, query: ActivityQuery) -> str` and `invalidate_user(user_id: UUID) -> None`.

- [ ] **Step 1: Write analytics user-scope and grouping tests**

```python
def test_activity_counts_group_by_category_for_authenticated_user(client, token_a, facts_for_two_users):
    response = client.get("/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30", headers=bearer(token_a))
    assert all(item["user_id"] is None for item in response.json().get("debug", []))
    assert response.json()["items"] == [{"category_id": str(facts_for_two_users.a_category_id), "category_name": "Running", "count": 2}]

def test_weekly_grouping_uses_iso_monday_buckets(client, token_a, facts):
    response = client.get("/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30&grouping=week", headers=bearer(token_a))
    assert response.json()["buckets"][0]["bucket_start_date"] == "2026-08-31"
```

- [ ] **Step 2: Write Redis cache tests**

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

- [ ] **Step 3: Write Redis degraded fallback tests**

```python
def test_redis_unavailable_queries_postgres_and_marks_cache_degraded(client, token_a, monkeypatch):
    monkeypatch.setattr(cache_module, "get_cached_result", lambda *args, **kwargs: (_ for _ in ()).throw(RedisError("down")))
    response = client.get("/api/v1/analytics/activity-counts?start_date=2026-09-01&end_date=2026-09-30", headers=bearer(token_a))
    assert response.status_code == 200
    assert analytics_cache_degraded_metric_value() == 1
```

- [ ] **Step 4: Verify RED**

Run: `python -m pytest services/analytics/tests -q`

Expected: FAIL before Analytics implementation exists.

- [ ] **Step 5: Implement analytics view and grants**

Ensure Event migration creates or replaces `events.analytics_event_facts` with only approved fields: event_id, user_id, category_id, category_name, mood, occurred_at, local_date, and location fields only if required. Grant SELECT on the view to `pawprints_analytics_ro`; do not grant broad Event table access.

- [ ] **Step 6: Implement Analytics routes and cache**

Require explicit inclusive `start_date` and `end_date`. Frontend presets are not accepted as backend presets. Query read-only view with `WHERE user_id = :current_user_id AND local_date BETWEEN :start_date AND :end_date`. Cache user-scoped results under `analytics:v1:user:{user_id}:ver:{version}:activity-counts:{filter_hash}` with TTL.

- [ ] **Step 7: Implement internal invalidation**

`POST /internal/analytics/users/{user_id}/invalidate` requires Event internal credentials and increments `analytics:user:{user_id}:version`. Failure returns a safe error for internal callers but Event Service treats invalidation as best effort.

- [ ] **Step 8: Verify GREEN**

Run: `python -m pytest services/analytics/tests services/event/tests packages/pawprints-common/tests -q`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add services/analytics services/event/migrations
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

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 test
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke
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
- Create: `apps/web/package.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
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

- [ ] **Step 1: Write auth client single-flight test**

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
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/web; npm test -- --run src/auth/AuthProvider.test.tsx`

Expected: FAIL before app/client exist.

- [ ] **Step 3: Implement Vite app and proxy**

Configure Vite dev server:

```typescript
server: {
  proxy: {
    "/api": "http://localhost:8080"
  }
}
```

The app uses relative `/api/v1/*` URLs only.

- [ ] **Step 4: Implement auth runtime state**

Keep access token in React state/module memory only. Do not use localStorage/sessionStorage/IndexedDB. On app start, call `POST /api/v1/auth/refresh`; if it succeeds, restore user and token.

- [ ] **Step 5: Verify GREEN**

Run: `cd apps/web; npm test -- --run src/auth/AuthProvider.test.tsx`

Expected: PASS.

- [ ] **Step 6: Commit**

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
- Test: `apps/web/src/events/TimelinePage.test.tsx`
- Test: `apps/web/src/media/MediaCarousel.test.tsx`

**Interfaces:**
- Produces `/timeline` route.
- Consumes category/event/media APIs.
- Produces `fetchMediaObjectUrl(mediaId: string) -> Promise<string>` and `revokeMediaObjectUrl(url: string) -> void`.

- [ ] **Step 1: Write Timeline and Blob lifecycle tests**

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
```

- [ ] **Step 2: Verify RED**

Run: `cd apps/web; npm test -- --run src/events/TimelinePage.test.tsx src/media/MediaCarousel.test.tsx`

Expected: FAIL before components exist.

- [ ] **Step 3: Implement Timeline default and navigation**

Default date is browser today. Include previous day, today, next day, date input, and prominent New Pawprint action. Render entries vertical and chronological.

- [ ] **Step 4: Implement Event form**

Required fields: title max 120, category_id, intended local datetime, timezone. Optional: description max 10,000, mood enum, location_name, latitude/longitude. Support quick category creation as explicit category API call before Event creation.

- [ ] **Step 5: Implement restricted Markdown**

Use `react-markdown`, `remark-gfm`, and `remark-breaks`. Disable raw HTML by not using `rehype-raw`; restrict components to `p`, `strong`, `em`, `del`, `ul`, `ol`, `li`, and `br`. Add toolbar buttons that wrap selected text with `**`, `*`, and `~~`.

- [ ] **Step 6: Implement private Media carousel**

Fetch `/api/v1/media/{media_id}` with `Authorization: Bearer <accessToken>`, convert `Blob` to `URL.createObjectURL`, render `<img src={objectUrl}>`, and revoke URLs on media change/unmount. Do not place Bearer tokens in image URLs.

- [ ] **Step 7: Implement edit/delete UX**

Store latest ETag from GET/create/update. Send `If-Match` on PATCH and DELETE. On 412, fetch current version and show manual review state. Do not optimistically delete before server 204.

- [ ] **Step 8: Verify GREEN**

Run: `cd apps/web; npm test -- --run src/events/TimelinePage.test.tsx src/media/MediaCarousel.test.tsx`

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
- Create: `packages/pawprints-common/pawprints_common/observability.py`
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

- [ ] **Step 3: Implement common observability**

Add structured logs with request_id, service, level, method, route template, status, latency, and safe error/event codes. Add Prometheus RED metrics with low-cardinality labels. Do not label user_id, event_id, filenames, diary/search content, raw URLs, locations, storage keys, or tokens.

- [ ] **Step 4: Add service health/readiness**

`/healthz` returns process liveness. `/readyz` checks required dependencies. Analytics readiness requires PostgreSQL/read-view availability; Redis unavailability reports degraded cache state through logs/metrics but does not fail readiness when DB fallback works.

- [ ] **Step 5: Provision Prometheus and Grafana**

Prometheus scrapes `auth:8000/metrics`, `event:8000/metrics`, `media:8000/metrics`, and `analytics:8000/metrics` on the internal Compose network. Grafana loads Prometheus datasource and `Pawprints Service Overview` dashboard automatically.

- [ ] **Step 6: Verify observability stack**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 up
curl http://localhost:9090/-/ready
curl http://localhost:3000/api/health
```

Expected: Prometheus ready and Grafana health endpoint returns OK. Service metrics are visible in Prometheus targets.

- [ ] **Step 7: Commit**

```bash
git add packages/pawprints-common services infra/prometheus infra/grafana compose.yaml
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

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 test
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

Run: `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke`

Expected: if any vertical-slice requirement is missing, smoke fails with the missing behavior named.

- [ ] **Step 3: Implement API-driven seed**

`demo/seed.py` uses public Nginx APIs only. It registers or reuses one demo user, logs in, creates 4-5 categories, creates 8-12 synthetic events across recent days/weeks using `Asia/Taipei`, uploads safe sample media when available, and optionally calls Search/Analytics to generate demo traffic. Credentials come from ignored local env values.

- [ ] **Step 4: Wire `dev.ps1 seed`, `start`, and `demo`**

`seed` runs only when explicitly called. `start` orchestrates setup, infrastructure startup, explicit migrations, application/monitoring startup, readiness, and smoke. `demo` runs `start` then `seed`. Neither command deletes volumes.

- [ ] **Step 5: Verify full demo path**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 down
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 start
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 seed
```

Expected: stack starts, migrations run explicitly, smoke passes through Nginx, seed runs through public APIs, Prometheus and Grafana are available, and existing DB/media volumes survive normal `down`.

- [ ] **Step 6: Update README**

Document:

```text
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 setup
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 up
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 migrate
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 smoke
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 seed
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 down
```

Also document the underlying `docker compose` commands for transparency, Nginx as the public boundary, Prometheus/Grafana local URLs, and that destructive reset is explicitly named and separate from `down`.

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

Run: `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 test`

Expected: PASS with all mandatory backend/common/security tests.

- [ ] **Step 2: Run frontend tests that exist**

Run: `cd apps/web; npm test -- --run`

Expected: PASS for implemented frontend tests. If no frontend tests were added beyond optional scope, document that only backend and smoke are mandatory.

- [ ] **Step 3: Run full stack smoke**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 down
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 start
```

Expected: setup, explicit migrations, readiness, and smoke complete successfully through Nginx.

- [ ] **Step 4: Verify observability demo endpoints**

Run:

```powershell
curl http://localhost:9090/-/ready
curl http://localhost:3000/api/health
```

Expected: Prometheus ready and Grafana health OK.

- [ ] **Step 5: Verify no future/non-goal implementation slipped in**

Run:

```powershell
rg -n "kubernetes|k8s|service mesh|opentelemetry|otel|s3|presigned|oauth|mfa|rbac|admin|category delete|activity tag|postgis|heic|gif|thumbnail|loki|alertmanager" .
```

Expected: matches appear only in docs/spec/plan future or non-goal sections, not active MVP implementation code.

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
