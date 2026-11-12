# Moonlight Photo Studio — Backend

FastAPI + MongoDB backend for the Moonlight Photo Studio memory-wall planner: accounts and
sessions, frame catalog and layout templates, photo uploads, the geometry/layout engine, saved
designs, and WhatsApp quote requests with shareable design reports.

The code base started as a copy of the SAF Studio backend. Phase 1 (2026-11-12) separated it:
Moonlight branding, its own database and configuration, local development storage, and a test
suite that can't reach real services. See [docs/ROADMAP.md](../docs/ROADMAP.md) for later phases.

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
uv run uvicorn app.main:app --reload --port 8000
```

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
| Catalog | `GET /frame-materials`, `GET /frames`, `GET /templates` |
| Photos | `POST /photos/upload`, `GET /photos`, `GET /photos/{id}/thumbnail`, `GET /photos/{id}/preview`, `DELETE /photos/{id}` |
| Geometry | `POST /geometry/validate-layout`, `/geometry/generate-layout`, `/geometry/regenerate`, `/geometry/redesign` |
| Designs | `POST /designs`, `GET /designs`, `GET/PATCH/DELETE /designs/{id}`, `POST /designs/{id}/versions` |
| Quotes | `POST /quotes/prepare`, `GET /quotes/{id}`, `GET /quotes/share/{token}`, `GET /quotes/share/{token}/preview`; short link `GET /q/{token}` |

Errors use one envelope: `{"error": {"code", "message", "details": [{"field", "issue"}], "timestamp"}}`.
Quote references are `MQ-YYYY-NNNN`. The live schema is at `/api/v1/openapi.json` (non-production).

## Quality gates

```bash
uv sync && uv lock --check
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

The test suite is **hermetic** ([tests/conftest.py](tests/conftest.py)): it never reads
`backend/.env`, pins every integration to an offline value, uses a temporary storage folder, and
fails any test that tries to reach a non-loopback host. The one live test,
`test_live_mongo_registration.py`, runs only if MongoDB is listening on localhost. It uses
the throwaway database `moonlight_studio_pytest_live` and drops it afterwards.

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
