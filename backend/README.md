# SAF Studio — Backend Service

Asynchronous Python/FastAPI backend for **SAF Studio**, supporting custom gallery wall curation, geometry layout solving, framing pricing, and quotation workflows.

## Technology Stack

- **Language:** Python 3.12+
- **Web Framework:** [FastAPI](https://fastapi.tiangolo.com/) (0.115+)
- **ASGI Server:** [Uvicorn](https://www.uvicorn.org/) (with standard uvloop & httptools)
- **Database Driver:** [PyMongo Async](https://pymongo.readthedocs.io/) (Official asynchronous MongoDB driver)
- **Data Validation & Settings:** [Pydantic v2](https://docs.pydantic.dev/latest/) & [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **Testing:** [Pytest](https://docs.pytest.org/) & [HTTPX](https://www.python-httpx.org/)
- **Linter & Formatter:** [Ruff](https://docs.astral.sh/ruff/)

---

## Directory Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entry & lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py      # Shared API dependencies (settings, db)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py        # Central API v1 router
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           └── health.py    # Liveness & readiness health probes
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Typed environment settings via pydantic-settings
│   │   ├── exceptions.py        # Custom domain exception classes
│   │   ├── handlers.py          # Global exception handlers (RFC error envelope)
│   │   └── logging.py           # Structured JSON/Text logging with credential masking
│   ├── db/
│   │   ├── __init__.py
│   │   ├── mongodb.py           # PyMongo Async connection manager & lifecycle
│   │   └── dependencies.py      # Database injection dependencies (get_db)
│   ├── models/                  # Internal database entity models (Phase 2+)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py            # Standard API error envelope schemas
│   │   └── health.py            # Health check response schemas
│   ├── repositories/            # Data access repositories (Phase 2+)
│   ├── services/                # Business services & calculation engines (Phase 2+)
│   └── utils/                   # Shared utility functions
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures & async test client
│   ├── test_config.py           # Configuration & CORS validation tests
│   ├── test_errors.py           # Exception normalization & sanitization tests
│   └── test_health.py           # Liveness & readiness endpoint tests
├── .env.example                 # Documented template environment configuration
├── .gitignore                   # Git exclusion rules
├── pyproject.toml               # Project dependencies, Ruff & Pytest config
└── README.md                    # Developer documentation
```

---

## Getting Started

### 1. Prerequisites
- Python 3.12 or higher.
- [uv](https://github.com/astral-sh/uv) (recommended) or standard `python -m venv`.
- MongoDB 7.0+ (running locally at `mongodb://localhost:27017` or via Docker).

### 2. Environment Setup

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Review and adjust settings in `.env` if necessary:

| Variable | Default Value | Description |
|---|---|---|
| `APP_NAME` | `SAF Studio API` | Application title |
| `ENVIRONMENT` | `development` | Environment (`development`, `staging`, `production`, `test`) |
| `DEBUG` | `true` | Enables Swagger UI and debug logs |
| `HOST` | `0.0.0.0` | Bind host |
| `PORT` | `8000` | Bind port |
| `API_V1_STR` | `/api/v1` | Prefix for version 1 API routes |
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection URI |
| `DATABASE_NAME` | `saf_studio` | Database name |
| `MONGODB_TIMEOUT_MS` | `5000` | Server selection and connection timeout |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173"]` | Allowed frontend origins |
| `JWT_SECRET_KEY` | `dev-insecure-jwt-secret-replace-in-production-min-32-chars` | Secret key for HMAC-SHA256 JWT access tokens |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | JWT access token lifespan |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Opaque refresh token lifespan |
| `REFRESH_COOKIE_NAME` | `refresh_token` | Name of the httpOnly refresh cookie |
| `REFRESH_COOKIE_SECURE` | `false` | Enable HTTPS Secure flag on cookies (`true` in prod) |
| `REFRESH_COOKIE_SAMESITE` | `lax` | SameSite cookie policy (`lax`, `strict`, `none`) |
| `GOOGLE_CLIENT_ID` | `""` | Google OAuth2 client ID for ID token validation |
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS`| `5` | Max login attempts before sliding rate limit locks |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS`| `300` | Rate limit sliding window (seconds) |
| `FORGOT_PASSWORD_RATE_LIMIT_MAX` | `3` | Max password recovery attempts |
| `FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SECONDS` | `900` | Password recovery sliding window |

### 3. Install Dependencies

Using `uv`:

```bash
uv pip install -e ".[dev]"
```

Or using standard `pip`:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -e ".[dev]"
```

---

## Running the Application

### Development Server (with Auto-Reload)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The service will start at `http://localhost:8000`.

### Interactive API Documentation
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON:** [http://localhost:8000/api/v1/openapi.json](http://localhost:8000/api/v1/openapi.json)

*(Note: API docs are automatically disabled when `ENVIRONMENT=production` and `DEBUG=false`)*.

---

## Health Check APIs

### 1. Liveness Probe
- **Endpoint:** `GET /api/v1/health/live`
- **Purpose:** Verifies the FastAPI application worker is responsive (Kubernetes/container liveness).
- **Behavior:** Operates independently of database connectivity.
- **Success Response (200 OK):**
  ```json
  {
    "status": "ok",
    "service": "saf-studio-api",
    "version": "0.1.0",
    "uptime_seconds": 45.2
  }
  ```

### 2. Readiness Probe
- **Endpoint:** `GET /api/v1/health/ready`
- **Purpose:** Verifies that the service can communicate with MongoDB.
- **Behavior:** Executes a lightweight `ping` command against MongoDB.
- **Success Response (200 OK):**
  ```json
  {
    "status": "ready",
    "service": "saf-studio-api",
    "database": {
      "connected": true,
      "status": "connected",
      "latency_ms": 1.45
    },
    "timestamp": "2026-11-07T12:00:00.000Z"
  }
  ```
- **Failure Response (503 Service Unavailable):**
  ```json
  {
    "error": {
      "code": "DATABASE_UNAVAILABLE",
      "message": "Database service is currently unreachable",
      "details": [
        {
          "field": "database",
          "issue": "MongoDB ping timed out or refused connection"
        }
      ],
      "timestamp": "2026-11-07T12:00:00.000Z"
    }
  }
  ```

---

## Testing & Quality Assurance

### Run the Pytest Suite
```bash
pytest -v
```

### Run Ruff Linter
```bash
ruff check .
```

### Run Ruff Formatter Check
```bash
ruff format --check .
```

---

## Authentication & Identity APIs (Phase 2)

Phase 2 implements production-grade authentication and session lifecycle management with official contracts `EP-AUTH-01` through `EP-AUTH-07`.

### Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register with name, email, phone (+91), password | No |
| `POST` | `/api/v1/auth/login` | Authenticate using email or phone and password | No |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token and issue fresh JWT access token | No (Cookie or Body) |
| `POST` | `/api/v1/auth/logout` | Revoke refresh token family and clear cookie | No (Cookie or Body) |
| `GET` | `/api/v1/auth/me` | Retrieve authenticated user profile | Yes (`Bearer <token>`) |
| `POST` | `/api/v1/auth/forgot-password` | Non-enumerating password reset initiation | No |
| `POST` | `/api/v1/auth/google` | Cryptographic Google ID token verification and sign-in | No |

### Security Mechanisms

1. **Argon2id Password Hashing:** Stored with salt and high memory cost (`m=65536, t=3, p=4`).
2. **Timing Attack Protection:** Constant-time dummy verification for unknown users on login prevents account enumeration via response latency.
3. **Rotating Refresh Tokens with Reuse Detection:**
   - Refresh tokens are cryptographically generated (32 bytes urlsafe base64).
   - Only their SHA-256 hash is persisted in MongoDB (`refresh_tokens` collection).
   - Sessions are grouped into a `family_id`. When a token is rotated, it is marked revoked.
   - If an already revoked token is replayed, all tokens within that `family_id` are immediately revoked.
4. **Secure Cookie Transport:**
   - Refresh token is delivered via `httpOnly`, `Path=/api/v1/auth`, `SameSite=Lax` cookie.
   - In production (`ENVIRONMENT=production`), the `Secure` flag is enforced.
5. **Rate Limiting:**
   - In-memory sliding-window rate limiting prevents credential stuffing (5 attempts per 5 minutes per IP/identifier).
6. **Google ID Token Verification:**
   - Uses official `google.oauth2.id_token.verify_oauth2_token` with audience and email verification.

---

## Catalogs & Templates APIs (Phase 3)

Phase 3 implements publicly accessible read-only catalogs for framing materials, moldings profiles, and gallery wall layout templates, conforming to contracts `EP-CAT-01`, `EP-CAT-02`, and `EP-TMPL-01`.

### Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/frame-materials` | Master catalog of materials (`wood`, `metal`, `synthetic`) with category & availability filters | Public |
| `GET` | `/api/v1/frames` | Commercial frame molding profiles, face dimensions, swatches, and linear pricing | Public |
| `GET` | `/api/v1/templates` | Pre-engineered gallery wall layout templates with slot coordinates and recommended wall sizes | Public |

### Database Seeding Mechanism

An idempotent seeder loads initial frontend materials, swatches, and templates into MongoDB without duplicating records:

```bash
# Clean or development seeding:
python -m app.db.seed_catalog

# Update existing records with latest seed values:
python -m app.db.seed_catalog --overwrite
```

**Seeded Collections:**
1. `frame_materials`: 4 master materials (Natural White Oak, Premium Plantation Teak, Anodized Aluminium, Engineered Polymer Composite).
2. `frame_moldings`: 4 commercial profiles including the 8 frontend wood finishes (`Walnut`, `Natural Oak`, `Ivory`, `Whitewash`, `Dark Teak`, `Honey`, `Golden Teak`, `Mahogany`) with hex swatch codes and face widths (resolving UI mismatch M8).
3. `layout_templates`: 10 gallery wall layouts matching frontend constants (`balanced-grid`, `creative-salon`, `centre-focus`, `minimal-row`, `classic-six`, `triptych`, `petite-salon`, `statement-centre`, `panorama-row`, `grand-quad`).

---

## Photo Management & Cloudflare R2 Storage (Phase 4)

Phase 4 implements user photograph upload, Pillow-driven validation and optimization, Cloudflare R2 cloud object storage via `boto3`, MongoDB metadata tracking, and secure signed media streaming conforming to `EP-PHOTO-01` through `EP-PHOTO-05`.

### Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/photos/upload` | Upload JPEG/PNG/WebP, EXIF auto-rotate, WebP preview (1600px) & thumbnail (300px), store in R2 & MongoDB | Bearer Token |
| `GET` | `/api/v1/photos` | Paginated listing of user's active photos with short-lived HMAC signed thumbnail & preview URLs | Bearer Token |
| `GET` | `/api/v1/photos/{id}/thumbnail` | Stream 300px WebP thumbnail via short-lived HMAC signature (`?sig=...&exp=...`) or Bearer token | Signed URL / Bearer |
| `GET` | `/api/v1/photos/{id}/preview` | Stream 1600px WebP preview via short-lived HMAC signature (`?sig=...&exp=...`) or Bearer token | Signed URL / Bearer |
| `DELETE` | `/api/v1/photos/{id}` | IDOR-safe photo deletion: marks `is_deleted=True` in MongoDB and purges binary objects from R2 | Bearer Token |

### Security & Storage Architecture

1. **Pillow Image Sanitization & Validation:**
   - Content sniffing via magic bytes (`image/jpeg`, `image/png`, `image/webp`).
   - Rejection of decompression bombs (`Image.MAX_IMAGE_PIXELS = 100_000_000`).
   - EXIF `Orientation` tag auto-rotation and metadata stripping.
   - Dimension validation: Minimum 300x300 px, maximum 8192x8192 px, max 25 MB.
2. **Cloudflare R2 Object Storage (`boto3`):**
   - Hierarchical keys: `users/{user_id}/photos/{photo_id}/original.ext`, `preview.webp`, `thumbnail.webp`.
   - Asynchronous threadpool execution (`asyncio.to_thread`) for non-blocking I/O.
   - Atomic rollback: If any R2 upload or MongoDB persistence step fails, partially uploaded R2 objects are cleaned up immediately.
3. **Short-Lived HMAC Signed URLs:**
   - Media streaming endpoints (`/thumbnail`, `/preview`) generate SHA-256 HMAC tokens over `photo_id:kind:expires_at` signed with `SECRET_KEY`.
   - Prevents unauthorized hotlinking while allowing frontend `<img src="...">` rendering without sending Authorization headers in DOM requests.
4. **Ownership Isolation (IDOR Protection):**
   - All write and read operations verify `user_id == current_user.id` or valid signature.
   - Cross-tenant access attempts return `403 Forbidden` or `404 Not Found` without disclosing resource existence.
5. **Rate Limiting:**
   - Sliding-window rate limiter limits photo uploads to 30 uploads per hour per user.

---

## Status & Test Suite

The automated test suite contains **114 passing tests** across Phases 1, 2, 3, and 4:
- `tests/test_health.py` (Liveness, readiness, DB down simulation)
- `tests/test_config.py` (CORS policies, masking, environment handling)
- `tests/test_errors.py` (RFC error envelope normalization)
- `tests/test_auth_register.py` (Registration, validation, duplicate handling)
- `tests/test_auth_login.py` (Email/phone login, bad password, account disabled)
- `tests/test_auth_tokens.py` (JWT claims, refresh rotation, replay detection, logout, `/me`)
- `tests/test_auth_google.py` (Google token verification, user creation & account linking)
- `tests/test_auth_password_reset.py` (Non-enumerating recovery flow)
- `tests/test_auth_security.py` (Argon2id hashing, rate limiting, NoSQL injection resistance)
- `tests/test_frame_materials.py` (Material listing, category filtering, availability, sorting, validation)
- `tests/test_frames.py` (Molding profiles, M8 hex swatches, material filtering, width ranges, validation)
- `tests/test_templates.py` (Template listing, slot geometries, category filtering, frame count range, ordering)
- `tests/test_catalog_seed.py` (Idempotent repeated seeding, non-overwrite protection, reference integrity)
- `tests/test_image_processing.py` (Pillow verification, MIME sniffing, WebP generation, decompression bomb defense)
- `tests/test_r2_storage.py` (R2 client upload, download, batch delete, 503 simulation)
- `tests/test_photo_upload.py` (Photo upload endpoint, validation, rate limiting, R2 failure rollback)
- `tests/test_photo_listing.py` (Photo listing endpoint, pagination, ownership isolation)
- `tests/test_photo_access.py` (HMAC signed URL access, expiration, tampering checks, Bearer auth)
- `tests/test_photo_delete.py` (Soft deletion, R2 object cleanup, IDOR protection)

All code passes `ruff check .` and `ruff format --check .` with zero errors.

Phase 5 is prepared to introduce **Geometry & Layout Engine** (`/api/v1/layouts/*`).

