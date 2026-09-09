# Pawprints Whole-System MVP Design Specification

Date: 2026-09-09
Status: Approved for implementation planning


## 1. Product Goal and MVP Anchor

Pawprints is a private personal journal and life activity tracker. Each life event is a "Pawprint": a structured journal entry that can appear on a daily chronological timeline, be searched later, and contribute to category-based activity-frequency analytics.

The MVP is an interview project with a one-day implementation target. It should demonstrate credible cloud-native architecture, service ownership, security, authorization, Redis caching, observability, testing, and a path to future deployment without adding distributed infrastructure the MVP does not need.

The non-negotiable demo path is:

1. Register.
2. Establish a login session immediately.
3. Create a user-owned Category.
4. Create a Pawprint.
5. Upload a few images.
6. View the event on the correct Daily Timeline in chronological order.
7. Expand the entry to view restricted-Markdown diary content and the Media carousel.
8. Edit the event using optimistic locking.
9. Find it through Search.
10. See its category reflected in Analytics.
11. Delete it.
12. Verify Timeline, Search, Media, and Analytics reflect deletion.

Two engineering/security proofs are also non-negotiable, even if primarily demonstrated through automated tests:

1. Cross-user isolation: User B cannot read, modify, delete, list, or retrieve User A's resources or media.
2. Optimistic locking: stale If-Match updates/deletes are rejected correctly.

Completeness of this spec does not mean every possible feature has equal priority. Implementation should get this vertical slice working end-to-end early, then deepen tests and supporting behavior around it.

## 2. Compact Decision Summary

- Architecture: lightweight microservices, separate deployable containers, synchronous HTTP, Docker Compose locally.
- Services: React frontend, Nginx API Gateway, Auth Service, Event Service, Media Service, Analytics Service, PostgreSQL, Redis, Prometheus, Grafana.
- Backend stack: Python, FastAPI, Pydantic, SQLAlchemy, Alembic, sync httpx, pytest, Pillow.
- Frontend stack: React, TypeScript, Vite, React Router, plain CSS, lucide-react.
- Gateway: path-based /api/v1/* routing through Nginx, no BFF, no business orchestration.
- Database: one local PostgreSQL database with separate schemas, roles, grants, and service-owned migrations.
- Auth: email/password, optional display name, Argon2id password hashes, short-lived access JWTs, opaque hashed rotating refresh tokens in HttpOnly cookies.
- JWT validation: services validate public endpoint JWTs authoritatively; Nginx remains edge hygiene.
- IDs: server-generated UUIDv4 exposed in APIs and stored as PostgreSQL uuid.
- Events: required title, category, intended local datetime, IANA timezone; backend derives occurred_at and local_date.
- Categories: Event Service-owned, user-owned, create/list/rename only, normalized uniqueness per user.
- Mood: nullable fixed enum: great, good, neutral, low, bad.
- Location: inline Event fields, explicit user input only, no EXIF-derived location.
- Markdown: restricted client-side Markdown rendering; raw HTML disabled.
- Media: Media Service owns metadata/local filesystem media storage, direct multipart upload, private Bearer-protected retrieval, JPEG/PNG/WebP only, max 5 images/event, max 5 MB/file, static images only.
- Analytics: category-based activity frequency using read-only PostgreSQL access to approved Event-owned views; Redis caches user-scoped aggregate results.
- Redis: degradable analytics result caching only, per-user cache version plus TTL and best-effort invalidation.
- Observability: privacy-safe structured logs, request IDs, health/readiness, Prometheus metrics, one provisioned Grafana dashboard.
- Testing: backend-heavy automated tests, P0 security regression tests, Docker Compose smoke verification.
- Developer workflow: PowerShell scripts/dev.ps1 task wrapper.

## 3. Architecture Overview

Pawprints uses lightweight microservices for the MVP. Each backend service is independently containerized and owns a clear API boundary. The MVP avoids message brokers, service mesh, Kubernetes, distributed tracing, and background workers.

Public browser traffic enters through Nginx. Nginx serves the built React app in production/demo mode and routes /api/v1/* requests to internal services. Backend service ports are private to the Compose network and are not exposed directly to the host/browser.

Service-to-service calls use synchronous HTTP through the private Compose network. Services use a consistent synchronous Python implementation style: ordinary FastAPI def endpoints, synchronous SQLAlchemy sessions, reusable synchronous httpx.Client instances with bounded timeouts, and blocking Pillow image processing.

## 4. Repository Layout

Conceptual monorepo layout:

```text
apps/
  web/
services/
  auth/
  event/
  media/
  analytics/
packages/
  pawprints-common/
infra/
  nginx/
  postgres/
  prometheus/
  grafana/
scripts/
  dev.ps1
docs/
  superpowers/
    specs/
    plans/
compose.yaml
.env.example
.gitignore
README.md
```

Each backend service owns its code, tests, Dockerfile, config, and where applicable its Alembic config/migrations. packages/pawprints-common is deliberately narrow and may contain only security/protocol primitives such as JWT verification, internal-service auth, an authenticated identity value type, and a minimal generic error envelope helper. It must not contain ORM models, repositories, service-specific settings, domain logic, or workflow orchestration.

## 5. Service Boundaries and Data Ownership

Auth Service owns users, password hashing, access-token issuance, refresh-token persistence/rotation/revocation, login sessions, logout, and current-user identity responses.

Event Service owns events, categories, event lifecycle, event/category authorization, timezone conversion, local_date, search, optimistic locking, category normalization, analytics-facing database views, and Event deletion orchestration.

Media Service owns media metadata, a private local filesystem media storage abstraction such as a LocalFileStorage adapter, upload validation, image decoding/re-encoding, EXIF stripping, display order, media retrieval, individual media deletion, and idempotent cleanup for an Event. Media Service verifies Event ownership through Event Service for upload/list/retrieve/delete paths that require user ownership context.

Analytics Service owns analytics API behavior and Redis analytics caching. For MVP, it reads Event-owned analytics views through a least-privilege read-only PostgreSQL role. It does not write Event data and does not receive broad access to diary descriptions. Long term, Analytics should move to its own replicated read model populated through outbox/event-driven mechanisms.

## 6. Data Model

All externally visible resource IDs are server-generated UUIDv4 values stored in PostgreSQL native uuid columns. UUIDs are not authorization. Ownership checks are mandatory.

### Auth Schema

auth.users:

- id: UUID primary key.
- email: required normalized login identifier, unique at database level.
- password_hash: Argon2id hash only.
- display_name: nullable, non-unique.
- created_at, updated_at.

Email normalization trims surrounding whitespace and applies consistent case normalization. It does not perform Gmail/provider-specific dot or plus-address normalization.

auth.refresh_tokens:

- id: UUID primary key.
- user_id: user UUID.
- token_hash: SHA-256 hash of the opaque high-entropy refresh credential.
- created_at, expires_at, revoked_at.
- replaced_by_token_id: optional rotation lineage.

### Event Schema

events.categories:

- id: UUID primary key.
- user_id: owner UUID from JWT subject.
- name: display name.
- normalized_name: case/space-normalized value for per-user uniqueness.
- version: integer starting at 1.
- created_at, updated_at.

Duplicate normalized category names are prevented per user. The same category name may exist for different users. Category deletion is out of MVP.

events.events:

- id: UUID primary key.
- user_id: owner UUID from JWT subject.
- category_id: required FK to Event Service-owned category.
- title: required, non-blank, maximum 120 characters.
- description: nullable Markdown source text, maximum 10,000 characters by default and configurable.
- mood: nullable enum: great, good, neutral, low, bad.
- location_name: nullable text.
- latitude: nullable coordinate, -90 to 90.
- longitude: nullable coordinate, -180 to 180.
- occurred_at: canonical UTC instant/timezone-aware timestamp.
- timezone: required IANA timezone name.
- local_date: backend-derived date from occurred_at + timezone.
- version: integer starting at 1.
- created_at, updated_at.

Latitude and longitude must both be present or both null. location_name may exist without coordinates, and coordinates may exist without location_name. Clients cannot set local_date directly.

Event-owned analytics views expose only fields needed for aggregation, such as event_id, user_id, category_id, current category name, mood, occurred_at, local_date, and limited location information if needed. They should not expose private diary content unless a future analytics feature requires it.

### Media Schema

media.event_media:

- id: UUID primary key.
- event_id: UUID of Event Service-owned Event, without cross-service DB FK.
- storage_key: generated private storage key.
- mime_type.
- file_size.
- display_order: persisted integer carousel order.
- created_at.

UNIQUE(event_id, display_order) protects persisted ordering. Media Service owns count/order invariants.

## 7. Time Semantics

Frontend collects intended local date/time plus browser-detected IANA timezone. Event Service validates the timezone, converts the local datetime to canonical occurred_at, and derives local_date. If occurrence time or timezone changes, Event Service recomputes both occurred_at and local_date.

Daily Timeline queries use user_id + local_date and order by occurred_at ascending. General Search defaults to occurred_at descending. "What did I do on September 9?" means the user's intended local calendar day, not a UTC boundary accident.

## 8. Authentication and Session Behavior

Accounts use email + password only, with optional display_name. Registration requires email/password, may accept display name, creates a user, establishes a login session, sets the refresh cookie, and returns an access token plus user.

Passwords use Argon2id through a mature library such as pwdlib. Policy: minimum 12 characters, maximum 128 characters, reject empty/all-whitespace passwords, no composition rules. Passwords are exact secrets: do not lowercase or trim them. Store only password hashes. Opportunistic password rehash after successful login is desirable if supported by the library.

Access JWTs:

- Lifetime: 15 minutes.
- Stateless; not persisted or blacklisted in MVP.
- Claims: minimal sub user UUID plus standard issuer/audience/expiry claims.
- Algorithm: RS256 asymmetric signing for the MVP. Auth Service owns the private signing key. Event, Media, and Analytics Services receive only the public verification key. Local setup generates the development key pair.
- Small clock-skew tolerance only.

Refresh tokens:

- Opaque high-entropy random values, not JWTs.
- Delivered only through HttpOnly cookie.
- Stored only as SHA-256 hashes in PostgreSQL.
- Rotated atomically on every successful refresh.
- Single-use: two concurrent refresh attempts with the same old token cannot both succeed.
- Absolute login-session lifetime: 7 days from login/register. Rotated replacements inherit remaining expiry; they do not extend the session.
- Logout revokes current refresh credential and clears cookie.

Register/login/refresh return access_token, token_type Bearer, expires_in 900, and user id/email/display_name. The refresh token is never returned in JSON. Credential-bearing auth responses use Cache-Control: no-store. Tokens are never placed in URLs/query strings.

Refresh cookie policy: HttpOnly, Secure in production/TLS, configurable false for localhost HTTP, preferably SameSite=Strict, path-scoped to /api/v1/auth where practical.

POST /api/v1/auth/refresh restores frontend runtime auth state after page reload. The frontend must single-flight concurrent refresh attempts inside one runtime. Cross-tab coordination is future work. Refresh/logout are POST-only and should perform simple Origin validation because they rely on automatically attached cookies.

Access JWTs live only in frontend runtime memory. They must never be persisted in browser localStorage, sessionStorage, IndexedDB, URLs, or query strings.

## 9. Public API Contracts

All public endpoints are routed through Nginx under /api/v1. Public protected endpoints validate end-user JWTs inside the owning FastAPI service. Ownership is derived from JWT sub, never client-provided user_id. Errors use the Pawprints error envelope.

### Auth Service

POST /api/v1/auth/register

- Public.
- Body: email, password, optional display_name.
- Creates user and login session.
- Success: 201, auth-session JSON, sets refresh cookie.
- Errors: 422 validation_failed, 409 email_already_registered or safe equivalent.

POST /api/v1/auth/login

- Public.
- Body: email, password.
- Success: 200, auth-session JSON, sets refresh cookie.
- Errors: generic 401 unauthorized/invalid credentials without revealing whether email exists.

POST /api/v1/auth/refresh

- Public cookie-authenticated endpoint.
- Requires refresh cookie and valid Origin.
- Rotates refresh token, returns auth-session JSON.
- Success: 200, new access token, rotated refresh cookie.
- Errors: generic 401 unauthorized or session expired; old/expired/revoked/unknown token state is not revealed.

POST /api/v1/auth/logout

- Public cookie-authenticated endpoint; access JWT may be absent/expired.
- Requires valid Origin.
- Revokes current refresh token if present and clears cookie.
- Success: 204 or 200.
- Errors should be safe and idempotent where practical.

GET /api/v1/auth/me

- Requires Authorization: Bearer access token.
- Returns user id, email, display_name.
- Errors: 401 unauthorized.

### Event and Category Service

FastAPI route registration must keep static Event routes such as /events/timeline and /events/search unambiguous. Register static routes before /events/{event_id}, and type event_id as UUID, so the literal path segments "timeline" and "search" cannot be parsed or reported as malformed Event IDs.

GET /api/v1/categories

- Requires access JWT.
- Lists current user's categories.
- Success: 200, ordered list including id, name, version.

POST /api/v1/categories

- Requires access JWT.
- Body: name.
- Creates user-owned category with normalized uniqueness.
- Success: 201.
- Errors: 409 category_name_exists, 422 validation_failed.

PATCH /api/v1/categories/{category_id}

- Requires access JWT and If-Match version ETag, formatted as a quoted integer such as If-Match: "1".
- Body: name.
- Atomic update scoped by id, user_id, and expected version; increments version.
- Success: 200, category JSON and new ETag.
- Errors: 404 resource_not_found for missing/foreign, 412 stale_version, 409 category_name_exists, 422 validation_failed.
- After successful rename, Event Service best-effort calls Analytics invalidation for the current user.
- Category deletion is not exposed in MVP.

POST /api/v1/events

- Requires access JWT.
- Body: title, category_id, intended local datetime, timezone, optional description, mood, location_name, latitude, longitude.
- Event Service verifies that category_id belongs to the authenticated user, validates time/location/mood/title/description limits, derives occurred_at and local_date.
- Success: 201, Event JSON and ETag.
- Errors: 404 resource_not_found for foreign/missing category, 422 validation_failed.
- After successful creation, Event Service best-effort calls Analytics invalidation for the current user.

GET /api/v1/events/{event_id}

- Requires access JWT.
- Returns current user's Event only, including version and ETag.
- Does not include media details; frontend calls Media API separately.
- Errors: 404 resource_not_found for missing/foreign.

GET /api/v1/events/timeline?date=YYYY-MM-DD

- Requires access JWT.
- Lists events for current user's local_date, ordered by occurred_at ASC.
- Summary shape includes time, title, category, mood, and location. It may include description for expanded reuse if inexpensive, but media remains separate.

GET /api/v1/events/search

- Requires access JWT.
- Query params: keyword, date, inclusive local_date range, category_id, mood, location, pagination.
- Keyword uses parameterized SQLAlchemy ILIKE over title, description Markdown source, and location_name.
- Category remains structured category_id, not text search.
- Queries are user-scoped at the database level.
- Default order: occurred_at DESC.

PATCH /api/v1/events/{event_id}

- Requires access JWT and If-Match version ETag, formatted as a quoted integer such as If-Match: "1".
- Partial update; resulting Event must satisfy invariants. Required fields cannot be cleared.
- If category_id is supplied, Event Service verifies that the referenced Category belongs to the authenticated user before applying the update.
- If occurrence time/timezone changes, recompute occurred_at and local_date.
- Atomic update scoped by id, user_id, expected version; increments version.
- After successful mutation, Event Service best-effort calls Analytics invalidation.
- Success: 200, Event JSON and new ETag.
- Errors: 404 resource_not_found, 412 stale_version, 422 validation_failed.

DELETE /api/v1/events/{event_id}

- Requires access JWT and If-Match version ETag, formatted as a quoted integer such as If-Match: "1".
- Event Service validates the end-user JWT, verifies ownership/version, calls Media cleanup, then performs final version-conditional hard delete.
- Success: 204.
- Errors: 404 resource_not_found, 412 stale_version, 5xx internal_dependency_failed if media cleanup fails.
- Analytics invalidation after successful delete is best-effort and does not roll back deletion.

### Media Service

POST /api/v1/media/events/{event_id}

- Requires access JWT.
- Multipart upload of one or more images; total request body limited by Nginx, per-file validation enforced by Media Service.
- Media Service authenticates as internal caller and asks Event Service to verify current user owns Event.
- Allowed: JPEG, PNG, WebP static images only.
- Limits: max 5 images per Event, max 5 MB per file, decoded-pixel limit around 30 MP configurable.
- Decode with Pillow, reject corrupt/non-image/unsupported/animated/resource-exhaustion images, apply EXIF orientation, re-encode to strip metadata, preserve image family where practical, generate storage keys.
- Count/order insertion is concurrency-safe with short per-Event DB serialization and UNIQUE(event_id, display_order).
- Success: 201, list of public media metadata ordered by display order.
- Errors: 404 resource_not_found, 409 media_limit_exceeded, 413 payload_too_large, 415 unsupported_media_type, 422 invalid_image.

GET /api/v1/media/events/{event_id}

- Requires access JWT and Event ownership verification.
- Returns public media metadata ordered by display_order ASC, then deterministic secondary ordering.
- Public Media JSON responses expose only safe fields such as media id, event id if useful, MIME type, normalized file size, display_order, and created_at. storage_key and local filesystem paths are internal Media Service implementation details and must never be exposed publicly.

GET /api/v1/media/{media_id}

- Requires access JWT.
- Media Service finds metadata, verifies Event ownership through Event Service, streams private image bytes.
- Does not expose private storage directory or storage path.
- Errors: 404 resource_not_found for missing/foreign.

DELETE /api/v1/media/{media_id}

- Requires access JWT.
- Verifies Event ownership, hard-deletes private file and metadata.
- Does not renumber remaining display_order values.
- Success: 204.

### Analytics Service

GET /api/v1/analytics/activity-counts

- Requires access JWT.
- Query params: explicit inclusive local_date start_date and end_date, optional category_id, grouping such as none/week/month.
- Frontend UI presets such as current month and last 30 days resolve to explicit start_date/end_date values using the browser's current local calendar context. The Analytics API treats that explicit range as authoritative and does not infer timezone-dependent presets or require a user timezone profile for the MVP.
- Weekly buckets use ISO weeks starting Monday. Monthly buckets use calendar months in the Event local_date calendar.
- Uses current user's UUID from JWT to scope every query.
- Reads only approved Event-owned analytics views using read-only DB credentials.
- Uses Redis user-scoped versioned cache keys.
- If Redis is unavailable but PostgreSQL is healthy, Analytics bypasses the cache and queries the read-only analytics view directly, while recording degraded cache state through safe logs and metrics.
- Success: 200, category counts and optional buckets with category_id/current category name/count.

## 10. Internal Service APIs and Auth

Internal endpoints are not routed through public Nginx and are reachable only over the private Compose network. They require static per-service internal credentials.

Requests include headers conceptually:

- X-Pawprints-Internal-Service: <caller-service>
- X-Pawprints-Internal-Token: <secret>

Receiving services validate the caller is known, compare secrets with constant-time comparison such as hmac.compare_digest, and verify the caller is authorized for that specific endpoint. A valid internal credential does not authorize all internal endpoints.

Nginx strips any client-supplied internal-service headers from public requests.

GET /internal/events/{event_id}/ownership or equivalent

- Owning service: Event Service.
- Callable by: Media Service.
- Requires valid Media internal credential and forwarded end-user JWT.
- Event Service validates user JWT and confirms whether current user owns Event.
- Returns positive ownership result or safe not-found/unauthorized equivalent.

POST /internal/media/events/{event_id}/cleanup

- Owning service: Media Service.
- Callable by: Event Service.
- Requires Event internal credential.
- Deletes all media files and metadata for Event idempotently. Already-absent media is success.
- Does not need user JWT because Event Service has already authorized the domain operation.

POST /internal/analytics/users/{user_id}/invalidate

- Owning service: Analytics Service.
- Callable by: Event Service.
- Requires Event internal credential.
- Increments the user's analytics cache version in Redis.
- Best-effort side effect; failure is logged and does not roll back Event mutation.

Future cloud hardening may replace static internal credentials with workload identity, short-lived service credentials, mTLS, service-mesh identity, and rotation.

## 11. Authorization and Privacy Rules

Object-level authorization is core. Events and categories belong to users. Media inherits ownership through its Event. Analytics is always user-scoped. Ownership is derived from authenticated identity, never from client-provided user_id.

Foreign-owned and truly missing private resources both return 404 resource_not_found where existence leakage would be harmful. Authorization failures must not reveal another user's resource version, media metadata, filename, storage key, diary content, or existence.

Services do not trust arbitrary identity headers from clients. Public FastAPI endpoints validate JWTs themselves. Internal calls authenticate service identity separately from end-user identity.

## 12. Optimistic Locking

Mutable Events and Categories use integer version columns starting at 1. GET responses include both JSON version and an ETag representing that version.

GET responses for single mutable resources include an ETag header formatted as the quoted integer version, such as ETag: "1". Update/delete operations require an If-Match header with the last observed quoted version, such as If-Match: "1". Missing If-Match should return 428 precondition_required where practical. Mutations are atomic, scoped by id, user_id, and expected version, and successful updates increment version atomically. Stale owner mutations return 412 stale_version. Missing/foreign resources return 404 resource_not_found before revealing concurrency information.

Event DELETE performs the final database delete with the same expected version even if version was checked earlier before Media cleanup.

## 13. Media Behavior

Media upload is separate from Event creation. If Event creation succeeds but image upload fails, the Event remains valid; frontend shows failed files and offers explicit retry.

Media Service validates byte size, decoded image, format, animation/multiframe status, decompression-bomb safety, decoded-pixel limit, and per-Event image count. It applies EXIF orientation before metadata stripping and re-encodes images to remove metadata. It preserves JPEG->JPEG, PNG->PNG, WebP->WebP where practical.

New uploads append after the current max display_order. Batch upload preserves multipart/input order. Deleting media does not renumber; gaps are acceptable. Manual reorder is out of MVP.

Concurrent upload protection is local to Media Service. Expensive image decode/validation should happen outside the short critical section where practical. The metadata transaction acquires a per-Event serialization mechanism such as a PostgreSQL transaction-level advisory lock keyed by event_id, recounts existing media, rejects batches exceeding 5 images, assigns consecutive display_order values, inserts metadata, and commits.

Storage-write and metadata consistency must be handled explicitly. A storage-write failure must not leave committed metadata. If normalized file storage succeeds but the later metadata transaction fails, Media Service should best-effort delete the newly written files before returning failure.

Local filesystem media storage is behind a storage interface, conceptually a LocalFileStorage adapter. The MVP storage path must be persistent outside the ephemeral container filesystem, preferably a Docker named volume or an explicitly ignored host data directory. Normal docker compose down / dev.ps1 down must not delete active Media storage, just as it must not delete PostgreSQL data. Any command that removes database or media volumes must be explicitly destructive and clearly named.

Future storage may use private S3-compatible object storage and short-lived presigned upload/download URLs.

## 14. Deletion Orchestration

Event Service owns Event lifecycle and coordinates Event deletion:

1. Nginx routes and forwards the public DELETE request without making the authoritative authz decision.
2. Event Service validates the end-user JWT, ownership, and expected If-Match version.
3. Event Service calls internal Media cleanup endpoint.
4. If cleanup fails, Event remains and deletion returns a retryable server failure.
5. If cleanup succeeds, Event Service performs final version-conditional hard DELETE.
6. If final Event delete fails after media cleanup, MVP accepts temporary Event-without-images partial failure.
7. After successful Event delete, Event Service best-effort invalidates Analytics cache.

Hard delete means removal from active PostgreSQL rows, Media metadata, and active media storage. Backup/snapshot retention is future production policy, not claimed immediate erasure.

## 15. Search

Search lives in Event Service. It supports composable user-scoped filters:

- keyword over title, description Markdown source, and location_name using SQLAlchemy-parameterized ILIKE.
- specific date or inclusive date range using local_date.
- category_id.
- mood.
- location_name match.
- simple pagination.

MVP uses ILIKE because mixed Chinese/English content makes language-tokenized full-text search premature. Evolution path: ILIKE, then PostgreSQL pg_trgm/GIN indexes, then language-aware full-text or dedicated search only when justified.

## 16. Analytics and Redis

MVP product analytics are category-based activity frequency. One Event counts as one activity occurrence. Queries group by category_id, not category free text, so category rename does not fragment history. Displaying the current category name for historical analytics is acceptable.

Analytics Service reads approved Event-owned analytics views through a least-privilege read-only database role. Every analytics query is scoped by authenticated user UUID.

Redis is used only for user-scoped analytics result caching. Cache keys use a per-user cache version:

```text
analytics:user:{user_id}:version = 4
analytics:v1:user:{user_id}:ver:4:activity-counts:{filter_hash}
```

Analytics cache TTL is configurable, default around 10 minutes. Event Service calls internal Analytics invalidation after successful event create/update/delete and category rename, after the authoritative database mutation succeeds. Invalidation increments the user's cache version. Failures are logged and do not roll back Event mutations; TTL bounds staleness.

Redis is a degradable cache dependency. If Redis cache read/write is unavailable but PostgreSQL is healthy, Analytics bypasses Redis and queries the read-only analytics view directly. Analytics readiness should not fail solely because Redis is unavailable when this fallback path works; it should report degraded cache state through privacy-safe logs and metrics.

Redis keys and cached results must never leak across users.

## 17. Frontend UX

Authenticated app shell routes:

- /timeline
- /search
- /analytics

Auth routes:

- /login
- /register

Timeline is the default authenticated landing view. It defaults to Today, allows selecting another local_date, and provides previous day/today/next day navigation. Timeline entries are vertical and chronological. Compact entries show time, title, category, mood, and location. Expanding inline shows restricted-Markdown diary content, Media carousel, and edit/delete actions. "New Pawprint" is prominent.

The Media carousel must preserve private Bearer-protected retrieval. A normal image src request cannot attach the runtime Authorization Bearer header, so the frontend API layer fetches image bytes from /api/v1/media/{media_id} with the access token, converts the response Blob to a URL.createObjectURL URL for rendering, and revokes object URLs when they are no longer needed. Media must not be made public merely to simplify image rendering.

Search is a separate view with keyword/date range/category/mood/location filters and expandable result presentation where practical.

Analytics is a lightweight user-facing view for category counts and simple weekly/monthly frequency summaries. It is distinct from Grafana operational monitoring.

Category management is not primary navigation. Users can create/select categories during Event entry. Full category management is future work.

Account controls are secondary, such as a user menu with logout.

Styling uses a small global CSS foundation with variables for colors, spacing, borders, radii, typography, and basic responsiveness. The visual tone should be calm, clean, warm, personal, and readable. No Tailwind, shadcn/ui, MUI, Ant Design, dark mode, animation framework, or complex effects for MVP.

Use semantic HTML, labels, real buttons, keyboard-usable controls, and image alt handling.

## 18. Frontend Error and Recovery UX

Default model is explicit/manual recovery, not blanket automatic retries or aggressive optimistic UI.

- Access-token 401: attempt one single-flight refresh; if successful, retry original request once; otherwise clear session and redirect to login.
- Media upload after Event creation: keep Event, show failed files, offer explicit retry.
- 412 stale_version: do not auto-retry mutation; reload current server version and let user review.
- Event delete: do not remove from UI before server confirms. If Media cleanup fails, show clear retryable deletion error.
- Expanded entry: if Event loads but Media fails, render diary content and show media-specific retry state.
- Analytics errors: show local retry state without breaking Timeline/Search.
- Validation: surface actionable field/file errors.
- GETs may expose manual retry; POST/PATCH/DELETE do not get blanket automatic retries.

## 19. Restricted Markdown

Event description stores Markdown source text. Event Service does not store or return generated HTML.

Frontend renders restricted Markdown client-side using mature libraries:

- react-markdown.
- remark-gfm primarily for strikethrough/lists.
- remark-breaks if practical for textarea-friendly line breaks.

Supported rendered subset: paragraphs/plain text, bold, italic, strikethrough, unordered lists, ordered lists, and line breaks. Raw HTML is disabled/escaped: no rehype-raw, no dangerouslySetInnerHTML. Markdown-embedded images, links, headings, tables, code blocks, task lists, iframes, scripts, and arbitrary HTML attributes are out of MVP.

Editor is a textarea with small toolbar buttons for bold, italic, and strikethrough; list helpers are optional if inexpensive.

## 20. Error Contract

Errors use a small Pawprints envelope:

```json
{
  "error": {
    "code": "stale_version",
    "message": "This Pawprint changed since you opened it.",
    "request_id": "..."
  }
}
```

Validation errors use the same envelope with optional sanitized details:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "Some fields are invalid.",
    "request_id": "...",
    "details": [
      { "field": "title", "message": "Title is required." }
    ]
  }
}
```

Frontend behavior depends on stable code, not message text. Messages must not expose stack traces, SQL details, topology, file paths, secrets/tokens, or another user's private data. FastAPI validation structures should be sanitized before exposure. Nginx-generated important failures, especially upload 413, should return JSON where practical. 401 Bearer failures preserve WWW-Authenticate: Bearer semantics.

Successful responses do not require a universal data wrapper.

## 21. Gateway, Same-Origin, and Dev Proxy

Production/demo:

- Nginx serves built React app.
- Nginx routes /api/v1/auth/*, /api/v1/events/*, /api/v1/categories/*, /api/v1/media/*, /api/v1/analytics/*.
- Browser sees frontend and API as same origin.
- React uses relative URLs such as /api/v1/events.

Nginx responsibilities: routing, forwarding Authorization/cookies/Set-Cookie, stripping identity/internal headers, security headers, request/body-size limits, future TLS termination and rate limiting. Media routes get a larger body limit, but Media Service enforces per-file/event limits.

Development:

- Vite runs with HMR on localhost.
- Vite proxies /api/* to local Nginx Gateway.
- Frontend still uses relative /api/v1 contract.
- Broad CORS is not primary. If direct cross-origin fallback exists, use explicit development-only origin allowlist and never wildcard credentialed CORS.

## 22. PostgreSQL, Roles, and Migrations

One local PostgreSQL instance contains one Pawprints database with separate schemas and roles:

- auth schema, written only by pawprints_auth_rw.
- events schema, written only by pawprints_event_rw.
- media schema, written only by pawprints_media_rw.
- analytics schema has no MVP persistent tables unless a real need appears.
- Analytics read-only role can SELECT only approved analytics views/fields.

Infrastructure bootstrap creates database-level resources: schemas, users/roles, and grants. Each service owns and runs Alembic migrations only for its own schema. Each service should use its own Alembic version table inside its schema where practical.

Migrations are explicit jobs separate from FastAPI startup. A top-level helper may orchestrate them sequentially, but must not become a central migration system.

No cross-service DB foreign keys. Event.category_id may use a normal FK because both tables are Event Service-owned.

## 23. Configuration and Secrets

Commit .env.example with variable names, safe defaults, and obvious placeholders. Real .env and generated secrets/keys are ignored by Git. Root .env is used for Compose substitution, but containers receive only explicitly listed variables they need.

JWT private keys, public keys, DB credentials, internal service tokens, cookie config, Redis config, and media limits are injected at runtime. Local setup generates the RS256 development key pair. Prefer generated key files mounted read-only; do not embed multiline private keys in .env; do not copy secrets into Docker image layers.

Services validate config at startup and fail fast. No hard-coded fallback secrets. Secrets must not appear in logs, exceptions, metrics labels, frontend bundles, or committed config. VITE_* variables are public browser config only.

Production hardening: secret manager, credential/key rotation, TLS, Secure cookies, managed DB credentials.

## 24. Observability

MVP includes observability as part of the demo.

- Structured privacy-safe logs: request ID, service, level, method, route template, status, latency, safe error/event codes.
- X-Request-Id generated/forwarded by Nginx and propagated across service-to-service calls.
- /healthz and /readyz endpoints. Analytics /readyz should treat PostgreSQL/read-view availability as required, while Redis cache availability is degradable if direct PostgreSQL fallback works.
- FastAPI services expose internal /metrics endpoints for Prometheus.
- Prometheus scrapes over the internal Compose network.
- Grafana and Prometheus may expose local host ports for demo.
- Provision one Grafana datasource and one small dashboard, "Pawprints Service Overview".

Core operational metrics: request rate/count, status/error rates, request duration, service scrape/availability. Low-cardinality, privacy-safe labels only. No user IDs, event IDs, filenames, diary/search content, locations, raw URLs, or private values as labels. Route labels use normalized templates.

Small Pawprints-specific metrics are desirable if inexpensive: Analytics cache hits/misses, Media upload successes/rejections, Analytics invalidation failures.

Prometheus is for operational observability, not product analytics.

Out of MVP: OpenTelemetry/distributed tracing, Loki/ELK, Alertmanager, many dashboards, infrastructure exporters unless time clearly allows.

## 25. Testing Strategy

Testing is backend-heavy and security-focused. The goal is meaningful proof of architecture, authorization, and consistency, not maximum UI test count.

Mandatory backend unit/service tests cover:

- JWT validation.
- Refresh-token hashing, rotation, concurrency, expiry, logout revocation.
- Argon2id password hashing and password policy.
- Category normalization.
- Timezone/local_date derivation.
- Mood/location validation.
- Optimistic-lock version behavior.
- Media validation, decoded-pixel limit, image-count/order rules.
- Analytics cache keys, user scoping, versioning, invalidation.
- pawprints-common security primitives.

Mandatory API/integration tests cover:

- register/login/refresh/logout/me.
- Event CRUD.
- Category create/list/rename.
- Search and filters.
- If-Match stale rejection.
- Media upload/list/retrieval/delete.
- Analytics aggregation and Redis cache behavior.
- Analytics Redis-degraded fallback to read-only PostgreSQL when Redis is unavailable.

P0 security regression tests verify:

- User B cannot read/update/delete User A's Events.
- User B cannot create an Event using User A's category_id.
- User B cannot PATCH one of User B's Events to reference User A's category_id.
- User B cannot modify User A's Categories.
- User B cannot upload Media to User A's Event.
- User B cannot list/retrieve/delete User A's Media.
- Analytics never aggregates another user's data.
- Redis cached analytics cannot leak across users.
- Authorization errors do not expose foreign resource/version details.

Frontend component/unit tests are optional for day one. If time allows, focus only on route guards, chronological Timeline rendering, entry expansion, media Blob URL lifecycle, and basic Event-form validation. Server-side validation remains authoritative.

Docker Compose smoke verification is mandatory: containers build/start, migrations apply, PostgreSQL/Redis are healthy in the normal demo stack, frontend reaches APIs through Nginx, and the core register/login/create-event/timeline path works through the full stack. If time remains, add one Playwright happy path.

Use Superpowers TDD workflow for suitable implementation tasks: failing test first, verify red, implement, verify green, refactor.

## 26. Developer Workflow and Demo Data

Use scripts/dev.ps1 as the PowerShell-friendly task entry point:

- setup: create/copy local config, generate missing JWT keys and development secrets, no seed data.
- migrate: run Auth/Event/Media service-owned Alembic migration jobs; stop on failure.
- up: start app and monitoring stack.
- test: run backend tests and any optional frontend tests that have been implemented.
- smoke: verify running stack through public Nginx boundary.
- seed: optional local demo seed through normal public APIs.
- down: stop stack without deleting volumes.
- optional start/demo: orchestrate explicit setup/infra/migrate/up/ready/smoke and optional seed.

Down must not delete PostgreSQL volumes. Any destructive reset command must be explicitly named.

Seed data is optional, disabled by default, separate from migrations/startup, and uses normal public APIs. It may create/reuse one demo user, 4-5 categories, 8-12 synthetic events across recent days/weeks, varied moods/locations, and safe demo images if available. Demo credentials come from ignored local config. Relative dates keep demos fresh. Seed traffic can populate Grafana metrics.

## 27. MVP Non-Goals

Out of one-day MVP:

- Kubernetes/k3s, service mesh, distributed tracing/OpenTelemetry.
- Message broker, transactional outbox implementation, background workers.
- S3/object storage, presigned URLs, managed PostgreSQL/RDS.
- TLS/Ingress beyond documented production hardening.
- OAuth/social login, email verification, password reset, MFA, RBAC/admin.
- Full refresh-token-family reuse detection, instant access-token revocation, sliding/remember-me sessions.
- Category deletion, category merge, aliases, archive behavior.
- Activity tags, separate Activity entity, semantic category deduplication.
- HEIC/HEIF, GIF, SVG, TIFF, thumbnails/resizing, malware scanning.
- Manual media reorder.
- PostGIS, geocoding, radius queries, automatic EXIF GPS extraction.
- Full-text search engine or language-aware text search.
- Dark mode, animation framework, rich WYSIWYG editor, broad Markdown support.
- Large dashboard collection, Loki/ELK, Alertmanager.
- Full mobile-specific UI.

## 28. Future Evolution

Future growth paths are documented but do not expand MVP scope:

- Move schemas to independent databases or managed database instances.
- Replace local filesystem media storage with private S3-compatible object storage and presigned flows.
- Add transactional outbox/event-driven idempotent Media cleanup and Analytics read-model replication.
- Add workload identity, mTLS, service-mesh identity, short-lived service credentials, and rotation.
- Add rate limiting at Gateway for auth endpoints.
- Add stricter CSP and richer CSRF defenses if cookie-authenticated flows expand.
- Add HEIC, thumbnails, resizing, malware scanning, and background media processing.
- Add richer analytics: running stats, mood trends, maps, location stats, yearly summaries.
- Add tags, category merge/aliases, saved locations, and PostGIS if product need appears.
- Add OpenAPI-generated frontend clients/types.
- Add OpenTelemetry tracing and more dashboards once operational complexity justifies it.

## 29. Review Check

This specification intentionally keeps future/cloud-native ideas visible while anchoring implementation priority on one polished vertical slice plus security and concurrency proofs. It should be reviewed for consistency before writing the implementation plan.
