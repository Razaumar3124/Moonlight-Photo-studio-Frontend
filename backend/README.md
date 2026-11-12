# Moonlight Photo Studio — Backend

FastAPI + MongoDB backend for the Moonlight Photo Studio memory-wall planner: accounts and
sessions, frame catalog and layout templates, photo uploads, the geometry/layout engine, saved
designs, and WhatsApp quote requests with shareable design reports.

The code base started as a copy of the SAF Studio backend. Phase 1 (2026-11-12) separated it:
Moonlight branding, its own database and configuration, local development storage, and a test
suite that can't reach real services. Phase 2 hardened security; Phase 3 aligned the API contract
and catalog with the planner. See [docs/ROADMAP.md](../docs/ROADMAP.md) for later phases.

## Stack

Python 3.12 · FastAPI · PyMongo async · Pydantic v2 / pydantic-settings · Argon2id · PyJWT ·
Pillow · boto3 (Cloudflare R2) · httpx (Resend, Groq) · Jinja2 (quote report) · pytest · Ruff ·
[uv](https://docs.astral.sh/uv/)

## Quick start

```bash
cd backend
uv sync                      # creates .venv with runtime + dev dependencies
cp .env.example .env         # then set SECRET_KEY and OTP_SECRET_KEY (see below)
uv run python -m app.db.seed_catalog          # idempotent: adds missing catalog/templates only
uv run uvicorn app.main:app --reload --port 8000 --no-proxy-headers
```

Always pass `--no-proxy-headers`. By default uvicorn rewrites the client address from
`X-Forwarded-For` for connections from 127.0.0.1, a second, hidden trust list that would let
local callers spoof their IP. Client-IP trust is configured in one place: `TRUSTED_PROXIES`.

- API: <http://localhost:8000/api/v1> · Swagger UI: <http://localhost:8000/docs>
  (docs are disabled when `ENVIRONMENT=production` and `DEBUG=false`)
- The frontend dev server proxies `/api` to port 8000 (`frontend/.env.example` → `API_PROXY_TARGET`).
- Requires a MongoDB 7+ server; the default is `mongodb://localhost:27017`, database `moonlight_studio`.

Generate each secret separately:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`uv sync` notes: the project is an application, not a package (`[tool.uv] package = false`), and
uses `link-mode = "copy"` because Windows rejects uv's hardlinks inside OneDrive folders.
Use `uv sync --no-dev` for production images.

## Configuration

All settings live in `backend/.env` (git-ignored; template: [.env.example](.env.example)) and are
read by [app/core/config.py](app/core/config.py). The file is located relative to `backend/`, so
the server behaves the same from any working directory.

With the template's defaults every integration is **offline**:

| Integration | Default (development) | To enable |
|---|---|---|
| MongoDB | `mongodb://localhost:27017` / `moonlight_studio` | `MONGODB_URL`, `DATABASE_NAME` |
| Object storage | `STORAGE_BACKEND=local` → `backend/storage/local/` | `STORAGE_BACKEND=r2` + `R2_*` |
| Password-reset email | `EMAIL_PROVIDER=mock` (code logged at DEBUG in development) | `EMAIL_PROVIDER=resend`, `RESEND_*` |
| Google Sign-In | disabled: `POST /auth/google` → `503` | `GOOGLE_CLIENT_ID` |
| Groq AI curator | `GROQ_ENABLED=false` (deterministic layouts only) | `GROQ_ENABLED=true`, `GROQ_API_KEY` |
| WhatsApp quotes | placeholder business number | `BUSINESS_WHATSAPP_NUMBER`, `PUBLIC_APP_URL` |

**Production guard.** With `ENVIRONMENT=production` the app refuses to start unless secrets are
unique and ≥ 32 characters, `DEBUG=false`, storage is R2 with credentials, email is Resend with
test mode off, Groq has a key when enabled, the WhatsApp number isn't the placeholder and
`PUBLIC_APP_URL` is https. Errors name the variables, never their values.

Startup logs the (credential-masked) database target and storage backend, and warns if the
built-in development `SECRET_KEY` is in use.

## Security model (Phase 2)

| Area | Behaviour |
|---|---|
| Sessions | Access token (JWT, 30 min) in the JSON body: the frontend keeps it **in memory only**. The refresh token is **only** an httpOnly, `SameSite` cookie on `REFRESH_COOKIE_PATH` (default `/api/v1/auth`); it never appears in a body and is never read from one. |
| Refresh rotation | `POST /auth/refresh` claims the token with one atomic `find_one_and_update`, so concurrent refreshes rotate exactly once. A request that loses the race within `REFRESH_REUSE_GRACE_SECONDS` (two tabs, a retry) gets an access token and no new cookie. Replaying a token after that, or after logout, revokes the whole token family. |
| CSRF | Endpoints that set or read the cookie (`register`, `login`, `google`, `refresh`, `logout`) require `X-CSRF-Protection: 1`, and a browser `Origin`/`Referer` must be in `CORS_ORIGINS`, `PUBLIC_APP_URL` or the API's own origin. Bearer-token endpoints need neither. |
| Client IP | `X-Forwarded-For` / `X-Real-IP` are only honoured when the socket peer is in `TRUSTED_PROXIES`, read right to left skipping trusted hops. `CF-Connecting-IP` alone is ignored. |
| Rate limits | Fixed windows in the `rate_limits` collection (atomic upserts, TTL index, SHA-256-hashed subjects), or bounded process memory (`RATE_LIMIT_BACKEND=memory`). Login: per IP + account (5/5 min), per account (20/15 min), per IP (30/5 min). Registration, code requests (per email and IP), code checks (per IP and per email), the reset step, uploads and quotes are limited too. 429 responses carry `Retry-After`. |
| Account enumeration | Unknown accounts cost the same Argon2id work as wrong passwords (a real dummy hash). Forgot-password answers identically for unknown emails; the email goes out after the response, and delivery errors are logged, never returned. |
| Revocation | A password reset revokes refresh sessions, and access tokens issued before it (sub-second `iat`) on both required and optional auth. |
| Request size | Bodies are capped while streaming, before buffering: `MAX_REQUEST_BODY_BYTES` (1 MiB) generally, `R2_MAX_UPLOAD_MB` for photos, `QUOTE_PREVIEW_MAX_MB` for quote previews. A declared `Content-Length` over the limit gets 413 before any body byte is read. |
| Errors & logs | Clients get the standard envelope with generic text. Driver, SDK and exception messages go to logs only, with credentials masked (including tracebacks); JSON logs never include raw log arguments. Validation errors never echo submitted values. |
| Health | `/health/live` and `/health/ready` (MongoDB ping only) are public and minimal. Detailed `GET /health` is open in development, otherwise it answers 404 without a matching `X-Health-Token` (`HEALTH_DIAGNOSTICS_TOKEN`). |
| Headers | `nosniff`, `X-Frame-Options: DENY`, deny-all API CSP, `Referrer-Policy`, `Permissions-Policy`, COOP; `Cache-Control: no-store` on `/auth/*`; HSTS in production. The shared quote report has its own CSP (no scripts), `Referrer-Policy: no-referrer` and `private, no-store`. CORS allows only the four headers the frontend sends. |

Behind a reverse proxy or load balancer, set `TRUSTED_PROXIES` to its address range, or every
client is counted as the proxy's single IP for rate limiting.

## Planner catalog (Phase 3)

[app/modules/catalog.py](app/modules/catalog.py) is the source of truth for every Memory Wall
option and rule, with stable IDs: frame sizes (`5x7` … `24x36`), wood finishes (`walnut`,
`natural-oak`, … with moulding face widths), mount colours, paint shades, layout styles
(`grid`, `salon`, `centre`, `row`), template slugs, units (`ft`, `in`, `cm`, `m`) and the planner
rules (wall 36–480 × 48–240 in, 1–16 frames, gap 0–12, mount 0–6, 6 in margin, 12 in above the
floor or above the sofa line, eye level 60 in). `GET /api/v1/catalog` publishes it.

- Designs, quotes, layout generation, validation and the share report all resolve IDs through
  it. Unknown IDs are rejected (422); nothing falls back to a default size or finish.
- The outer frame size is always opening + mounts + 2 × the finish's moulding face, computed
  on the server.
- IDs are permanent. Legacy values in stored data (SAF finish IDs, `focal_center`/`triptych`
  categories, `mm`, older limits) are still read and displayed; they are never migrated.
- The frontend mirrors the catalog in `features/memory-wall/constants.ts` until Phase 5 loads it;
  `tests/test_catalog_contract.py` fails if the two (or the endpoint map) drift. Change both
  sides together.

## Local development storage

`STORAGE_BACKEND=local` stores photos and quote previews under `LOCAL_STORAGE_PATH` (default
`backend/storage/local/`, git-ignored) through the same interface as R2
([app/storage/](app/storage/)):

- object keys are validated and confined to the storage root (no `..`, absolute or backslash paths);
- writes are atomic (temp file + rename);
- files are never served as a static folder. Photo thumbnails/previews keep their existing signed
  URLs, and presigned URLs (e.g. the quote preview in `GET /quotes/{id}`) become
  `/api/v1/storage/local/{key}?exp=…&sig=…`: HMAC-SHA256 signed, expiring, `404` on any mismatch.
  The route always `404`s when R2 is active.

## Database

Collections and indexes are created at startup. The catalog seeder never removes data:

```bash
uv run python -m app.db.seed_catalog              # add missing materials, moldings, templates
uv run python -m app.db.seed_catalog --overwrite  # also refresh existing seed records (keeps IDs)
uv run python scripts/verify_atlas.py             # connectivity, indexes, R/W probe, seed check
```

Both print the masked target first. Check it before running them against a shared cluster.

## API overview (`/api/v1`)

| Area | Endpoints |
|---|---|
| Health | `GET /health/live`, `GET /health/ready`, `GET /health` |
| Auth | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/google`; `GET /auth/me`; `POST /auth/forgot-password`, `/auth/forgot-password/verify`, `/auth/forgot-password/reset` |
| Catalog | `GET /catalog`, `GET /frame-materials`, `GET /frames`, `GET /templates` |
| Photos | `POST /photos/upload`, `GET /photos` (signed thumbnail + preview URLs), `GET /photos/{id}/thumbnail`, `GET /photos/{id}/preview`, `DELETE /photos/{id}` (409 `PHOTO_IN_USE` while a saved design uses it) |
| Geometry | `POST /geometry/validate-layout`, `/geometry/generate-layout`, `/geometry/regenerate`, `/geometry/redesign` |
| Designs | `POST /designs`, `GET /designs`, `GET/PATCH/DELETE /designs/{id}`, `POST /designs/{id}/versions` |
| Quotes | `POST /quotes/prepare` (optional `Idempotency-Key`; the quote must match the saved design), `GET /quotes/{id}`, `GET /quotes/share/{token}`, `GET /quotes/share/{token}/preview`; short link `GET /q/{token}` |

Errors use one envelope: `{"error": {"code", "message", "details": [{"field", "issue"}], "timestamp"}}`.
Notable codes: `CSRF_VALIDATION_FAILED` (403), `RATE_LIMIT_EXCEEDED` (429 + `Retry-After`),
`PAYLOAD_TOO_LARGE` (413), `TOKEN_REVOKED` / `TOKEN_EXPIRED` / `INVALID_TOKEN` (401),
`DATABASE_UNAVAILABLE` / `STORAGE_UNAVAILABLE` (503), `GOOGLE_AUTH_NOT_CONFIGURED` (503).
Quote references are `MQ-YYYY-NNNN`. The live schema is at `/api/v1/openapi.json` (non-production).

## Quality gates

```bash
uv sync && uv lock --check
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

The test suite is **hermetic** ([tests/conftest.py](tests/conftest.py)): it never reads
`backend/.env`, pins every integration to an offline value, uses a temporary storage folder, and
fails any test that tries to reach a non-loopback host. The live tests
(`test_live_mongo_registration.py`, `test_live_mongo_security.py`) run only if MongoDB is
listening on localhost; they use throwaway `moonlight_studio_pytest_live*` databases and drop
them afterwards. `test_security_hardening.py` holds the Phase 2 security regression suite.
`test_catalog_contract.py` holds the Phase 3 catalog, contract and validation regression suite.

## Layout

```text
backend/
├── app/
│   ├── main.py            # app factory, lifespan (indexes), CORS, /q/{token} redirect
│   ├── api/               # dependencies.py + v1/router.py + v1/endpoints/*
│   ├── core/              # config, security (Argon2id, JWT, OTP, signatures), errors, logging
│   ├── db/                # MongoDB manager, catalog seeder
│   ├── integrations/      # Groq client
│   ├── models/ schemas/   # MongoDB documents / API request-response models
│   ├── modules/geometry/  # layout engine (mirrors the frontend's)
│   ├── repositories/      # data access per collection
│   ├── services/          # business logic (auth, photos, designs, quotes, email, WhatsApp…)
│   ├── storage/           # ObjectStorage protocol, R2Storage, LocalStorage
│   └── templates/         # quote_report.html
├── scripts/verify_atlas.py
├── tests/                 # pytest suite + in-memory fakes
├── .env.example
└── pyproject.toml
```
