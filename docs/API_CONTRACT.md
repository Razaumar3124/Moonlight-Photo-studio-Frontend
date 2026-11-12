<!--
  OWNER: backend. Regenerated from the implementation on 2026-11-12 (Backend Phase 3) and
  checked against the live OpenAPI schema (/api/v1/openapi.json in non-production). It replaces
  the 2026-11-05 contract received from the SAF-era backend; §11 lists what changed.
  Frontend mirror: frontend/src/types/api/ (one file per section) and services/endpoints.ts.
  Open questions: docs/API_ALIGNMENT.md. Change process: update this file, the TS types and the
  endpoint map in the same PR. backend/tests/test_catalog_contract.py checks that every path
  in endpoints.ts exists and that the planner catalog matches the frontend constants.
-->

# Moonlight Photo Studio – API Contract (v1)

## 1. Conventions

### 1.1 Basics

| Topic | Rule |
| --- | --- |
| Base URL | `/api/v1` (the frontend dev server proxies `/api` to FastAPI) |
| Format | JSON, UTF-8. Uploads use `multipart/form-data` |
| IDs | MongoDB ObjectIds as 24-character hex **strings** (`"672cf3a9e4b0123456789def"`). Catalog entries use stable slugs (`12x16`, `natural-oak`, `balanced-grid`) |
| Time | ISO-8601 UTC strings |
| Field names | `snake_case`. The one exception is quote `design_data`, which is the planner's own camelCase state (§8.1) |
| Money | No online pricing. The studio prices each design on WhatsApp. Catalog prices are decimal strings (`"22.00"`) |
| Lists | Catalog lists return `{ items, total }`. `GET /designs` adds `page`, `page_size`, `total_pages`; `GET /photos` adds `page`, `page_size` |

### 1.2 Authentication

- **Access token**: a JWT (30 min) in `tokens.access_token`, sent as `Authorization: Bearer <token>`. The frontend keeps it in memory only.
- **Refresh token**: an httpOnly, `SameSite` cookie scoped to `/api/v1/auth`. It never appears in a response body and is never read from one.
- **CSRF**: the cookie endpoints (`register`, `login`, `google`, `refresh`, `logout`) require `X-CSRF-Protection: 1`. A browser `Origin` must be an allowed origin. `apiClient` sends the header on every non-GET request.
- **Auth levels** used below: **public**, **bearer** (401 without a valid token), **optional** (works signed out; a token, if sent, must be valid).

### 1.3 Units and geometry

All lengths are **inches**, origin at the wall's top-left corner, with y growing downwards. The customer's unit (`ft`, `in`, `cm`, `m`) is stored as `display_unit` and only affects how text is displayed. Conversion: 1 ft = 12 in, 1 in = 2.54 cm, 1 m = 39.3701 in.

The planner rules (§3.1 `rules`) are the server's validation rules:

| Rule | Value |
| --- | --- |
| Wall width × height | 36–480 × 48–240 in |
| Frames per design / quote / layout request | 1–16 |
| Gap between frames | 0–12 in |
| Mount (mat) per side | 0–6 in |
| Side and ceiling margin | 6 in |
| Lowest point above the floor | 12 in. With the reference sofa shown: sofa top (14.57 in) + 8 in = 22.57 in |
| Eye level (arrangement centre) | 60 in |
| Outer frame size | photo opening + mount on both sides + finish `profile_inches` on both sides |

### 1.4 Errors

Every error, including validation, auth, CSRF, size limits and unhandled 500s, uses one envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Layout geometry violates wall boundaries or contains invalid dimensions.",
    "details": [{ "field": "items.f1", "issue": "Frame 'f1' extends beyond the safe wall boundaries or furniture clearance." }],
    "timestamp": "2026-11-12T09:00:00.000000+00:00"
  }
}
```

`details[].field` is the request field path, dotted, without a `body`/`query` prefix. A top-level field keeps its plain name (`email`, `category`); nested ones look like `wall.width_inches`, `items.0.matting.color_id` or, for quotes, `design_data.frames.0.sizeId`. Fit problems on a saved version use `items.<item_id>`. Messages never echo submitted values, stack traces or driver errors.

| Status | Codes |
| --- | --- |
| 400 | `BAD_REQUEST` |
| 401 | `UNAUTHORIZED` (no token), `INVALID_CREDENTIALS` (same for unknown account and wrong password), `INVALID_TOKEN`, `TOKEN_EXPIRED`, `TOKEN_REVOKED`, `INVALID_GOOGLE_TOKEN` |
| 403 | `FORBIDDEN` (someone else's resource), `ACCOUNT_DISABLED`, `CSRF_VALIDATION_FAILED` |
| 404 | `RESOURCE_NOT_FOUND` |
| 409 | `ACCOUNT_ALREADY_EXISTS` (`details[].field` = `email` or `phone`), `PHOTO_IN_USE` (deleting a photo that saved designs still use) |
| 413 | `PAYLOAD_TOO_LARGE` (bodies over 1 MiB; photos over 25 MB; quote previews over 15 MB) |
| 422 | `VALIDATION_ERROR` |
| 429 | `RATE_LIMIT_EXCEEDED`, with a `Retry-After` header in seconds |
| 500 | `INTERNAL_SERVER_ERROR` |
| 503 | `DATABASE_UNAVAILABLE`, `STORAGE_UNAVAILABLE`, `GOOGLE_AUTH_NOT_CONFIGURED` |

---

## 2. Authentication (`/auth`)

| Endpoint | Auth | Body → Response |
| --- | --- | --- |
| `POST /auth/register` | public + CSRF | `{ full_name, email, phone, password }` → **201** `{ user, tokens }` + refresh cookie |
| `POST /auth/login` | public + CSRF | `{ password }` plus one of `email`, `phone` or `identifier` → `{ user, tokens }` + cookie |
| `POST /auth/google` | public + CSRF | `{ id_token }` → `{ user, tokens }` + cookie. 503 if Google sign-in isn't configured |
| `POST /auth/refresh` | cookie + CSRF | → `AuthTokens`. The cookie is rotated |
| `POST /auth/logout` | cookie + CSRF | → **204**. The session is revoked and the cookie cleared |
| `GET /auth/me` | bearer | → `User` |
| `POST /auth/forgot-password` | public | `{ email }` → `{ message, cooldown_seconds }`. Same answer for unknown emails |
| `POST /auth/forgot-password/verify` | public | `{ email, otp }` → `{ reset_token, expires_in_seconds }`. 422 for a wrong or expired code |
| `POST /auth/forgot-password/reset` | public | `{ reset_token, new_password }` → `{ message }`. Revokes every session |

- **`User`**: `{ id, email, full_name, phone | null, role, is_active, created_at }`. The same full shape comes from register, login, Google and `/me`.
- **`AuthTokens`**: `{ access_token, token_type: "bearer", expires_in }`.
- **Rules**:
  - `full_name` is 2–100 characters (letters, spaces, hyphens, apostrophes).
  - `phone` is an Indian mobile number (10 digits or `+91…`).
  - `password` is 8–128 characters with at least one letter and one digit.
  - Email and identifier are at most 254 characters.
- **Concurrent refresh**: two tabs refreshing at once both succeed (within 30 s). Replaying an old refresh token revokes the whole session family.
- **Rate limits**:
  - Login: per IP + account 5 / 5 min, per account 20 / 15 min, per IP 30 / 5 min.
  - Register, code requests, code checks and the reset step are limited as well.

---

## 3. Catalog

### 3.1 `GET /catalog` (public, `Cache-Control: public, max-age=300`)

The planner catalog is the **source of truth** for every option the Memory Wall offers. Designs and quotes store these IDs; IDs are permanent.

```json
{
  "version": "2026-11-12",
  "frame_sizes": [{ "id": "12x16", "label": "12 x 16 inches (Atelier Classic Recommended)", "width_inches": 12, "height_inches": 16, "recommended": true }],
  "frame_finishes": [{ "id": "natural-oak", "label": "Natural Oak", "hex": "#916843", "profile_inches": 1.0 }],
  "mount_colors": [{ "id": "museum-white", "label": "Museum White", "hex": "#F4F3F3" }],
  "paint_shades": [{ "id": "warm-cream", "label": "Warm Cream", "hex": "#EFDECA" }],
  "layout_styles": [{ "id": "grid", "label": "Grid" }, { "id": "salon", "label": "Salon" }, { "id": "centre", "label": "Centre" }, { "id": "row", "label": "Row" }],
  "template_ids": ["balanced-grid", "creative-salon", "…"],
  "wall_units": ["ft", "in", "cm", "m"],
  "gap_units": ["in", "cm"],
  "rules": { "eye_level_inches": 60, "wall_margin_inches": 6, "min_bottom_inches": 12, "sofa_top_from_floor_inches": 14.5689, "sofa_clearance_inches": 8, "wall_width_inches": { "min": 36, "max": 480 }, "wall_height_inches": { "min": 48, "max": 240 }, "gap_inches": { "min": 0, "max": 12 }, "mat_inches": { "min": 0, "max": 6 }, "mat_step_inches": 0.5, "frame_count": { "min": 1, "max": 16 }, "variant_count": 3 }
}
```

| List | IDs |
| --- | --- |
| Frame sizes (portrait; landscape swaps the sides) | `5x7`, `8x10`, `11x14`, `12x16` (recommended), `16x20`, `18x24`, `20x30`, `24x36` |
| Wood finishes (`profile_inches`) | `walnut` 1, `natural-oak` 1, `ivory` 0.875, `whitewash` 0.875, `dark-teak` 1, `honey` 1, `golden-teak` 1.125, `mahogany` 1.125 |
| Mount colours | `museum-white`, `antique-white`, `black`, `crimson` |
| Paint shades | `ivory-mist`, `warm-cream`, `sand`, `peach-blush`, `charcoal`, `stone-grey`, `cloud-grey` |
| Layout styles | `grid`, `salon`, `centre`, `row` (legacy `focal_center`, `center`, `linear` and `triptych` are accepted and normalised) |

Unknown IDs are rejected with 422 (`"Unknown frame size; see GET /catalog frame_sizes"`). The server never substitutes a default.

### 3.2 Materials and mouldings (public)

- **`GET /frame-materials?category&available_only`** → `{ items: FrameMaterial[], total }`
  - `category` is `wood`, `metal` or `synthetic`.
  - Each material: `{ id, code, name, category, finish, base_price_per_linear_inch, waste_factor_percentage, thumbnail_url, is_available }`.
- **`GET /frames?material_id&color&min_width&max_width`** → `{ items: FrameMolding[], total }`
  - Each moulding: `{ id, sku, name, material_id, material_name, profile_width_inches, profile_depth_inches, rabbet_depth_inches, price_per_linear_inch, available_colors: [{ id, name, hex, profile_in }], thumbnail_url, is_active }`.
  - Wood colours use the catalog finish IDs.

---

## 4. Layout templates — `GET /templates?category&min_frames&max_frames` (public)

```json
{
  "items": [{
    "id": "672522012e5c6a1b2c3d5001", "slug": "balanced-grid", "name": "Balanced Grid",
    "description": "Nine Atelier Classic frames in a calm, even 3 × 3 grid.",
    "category": "grid", "gap_inches": 3.0,
    "min_wall_width_inches": 80, "min_wall_height_inches": 60,
    "recommended_wall_width_inches": 120, "recommended_wall_height_inches": 96,
    "slots_count": 9,
    "slots": [{ "slot_id": "slot-1", "relative_x_ratio": 0.35, "relative_y_ratio": 0.38,
                "default_photo_width_inches": 12, "default_photo_height_inches": 16,
                "aspect_ratio": 0.75, "size_id": "12x16", "orientation": "portrait" }],
    "thumbnail_url": "/static/templates/balanced-grid.webp"
  }],
  "total": 10
}
```

- **`category`** is a planner layout style. A legacy name used as a filter (`triptych` → `row`, `focal_center` → `centre`) is accepted; any other unknown name returns 422.
- **Slot sizes**: `size_id` and `orientation` give each slot's size in the catalog. `size_id` is `null` for non-standard sizes.
- **`gap_inches`** is `null` on templates seeded before 2026-11-12. Run `python -m app.db.seed_catalog --overwrite` to refresh them.

---

## 5. Photos (bearer, owner only)

| Endpoint | Result |
| --- | --- |
| `POST /photos/upload` (multipart `file`) | **201** `Photo` |
| `GET /photos?page&page_size` (≤ 100) | `{ items: PhotoSummary[], total, page, page_size }`, newest first. Each item has fresh signed `thumbnail_url` **and** `preview_url` |
| `GET /photos/{id}/thumbnail` (300 px), `/preview` (1600 px) | Image bytes. These are **signed, short-lived URLs**, usable in `<img src>` without the Bearer header |
| `DELETE /photos/{id}` | **204** (soft delete). **409 `PHOTO_IN_USE`** while any live (not deleted) design uses the photo in any of its versions; the message says how many. Delete those designs first |

- **`Photo`**: `{ id, user_id, original_filename, mime_type, file_size_bytes, width_px, height_px, aspect_ratio, suggested_orientation, thumbnail_url, preview_url, created_at }`. `PhotoSummary` is a subset of it.
- **Accepted files**:
  - JPEG, PNG or WebP, detected from the file content.
  - At most 25 MB, sides 300–8192 px, EXIF orientation applied.
- **Rate limit**: uploads are limited per user.

---

## 6. Geometry & layout engine (optional auth)

The engine is the server-side twin of the planner's layout code, with the same rules (§1.3).

- **`POST /geometry/validate-layout`**: `{ wall, frames: [{ item_id, outer_x_inches, outer_y_inches, outer_width_inches, outer_height_inches }] }` (1–16 frames).
  - Returns **200** `{ is_valid, bounding_box, wall_coverage_percentage, errors[], warnings[], calculated_items[] }`.
  - Problems never cause an error response. Collisions and boundary failures arrive in `errors[]` as `{ code, message, item_ids }`:
    - `GEOMETRY_COLLISION_DETECTED`
    - `GEOMETRY_OUT_OF_BOUNDS`
    - `GEOMETRY_INVALID_DIMENSIONS`
  - Warnings: `LOW_COVERAGE`, `TOO_WIDE`. 422 is only for malformed payloads.
- **`POST /geometry/generate-layout`**: `{ wall, frames[], layout_style?, spacing_inches (0–12, default 3), engine_mode ("geometric" | "smart_llm"), seed?, variant (0–2) }`.
- **`POST /geometry/regenerate`**: `{ wall, frames[], layout_style, current_seed, current_variant, spacing_inches }`, for the same style.
- **`POST /geometry/redesign`**: `{ wall, frames[], current_layout_style, spacing_inches, engine_mode }`, for a different style.
- **Responses**:
  - All three return `{ layout_type, variant, seed, bounding_box, wall_coverage_percentage, fits, items: PlacedItem[] }`.
  - Generate and redesign add `engine_used` and `ai_rationale`; generate also adds `warnings[]`.
- **Shapes**:
  - `wall`: `{ width_inches (36–480), height_inches (48–240), margin_inches = 6, has_sofa = false, eye_level_height_inches = 60 }`.
  - `frames[]`: `{ item_id, photo_id?, size_id?, finish_id?, orientation, photo_width_inches?, photo_height_inches?, frame_profile_width_inches?, matting? }`.
    - `size_id` and `finish_id` set the opening and moulding from the catalog. Explicit values that contradict them return 422.
    - Frames don't need photos (empty placeholders work).
  - `PlacedItem`: `{ item_id, photo_id, outer_x/y/width/height_inches, photo_x/y/width/height_inches }`.
- `bounding_box` is `{ x, y, width, height }` everywhere.

---

## 7. Designs (bearer, owner only; another user's design → 403)

| Endpoint | Body → Response |
| --- | --- |
| `POST /designs` | `{ title (1–100), description? (≤ 500), wall? }` → **201** `Design` |
| `GET /designs?page&page_size&status&search&sort` | `{ items: DesignListItem[], total, page, page_size, total_pages }`. `sort` is `updated_at`, `created_at` or `title` with `:asc` or `:desc` |
| `GET /designs/{id}` | `DesignDetail` (with `current_version`) |
| `PATCH /designs/{id}` | `{ title?, description?, status? ("draft" \| "saved" \| "ordered"), wall? }` → `Design`. `wall` replaces the whole wall |
| `DELETE /designs/{id}` | **204** (soft delete; photos are kept) |
| `POST /designs/{id}/versions` | `SaveDesignVersionRequest` → **201** `DesignVersionSummary` |

**Wall (input)**: `{ width_inches (36–480), height_inches (48–240), paint_id?, color_hex, texture, display_unit ("ft" | "in" | "cm" | "m"; "mm" kept for older clients), has_sofa }`. A `paint_id` sets `color_hex` from the catalog. The stored wall comes back with the same fields, and output isn't range-checked, so designs saved under older rules still load.

**`SaveDesignVersionRequest`**:

```json
{
  "layout_type": "grid",
  "template_id": "balanced-grid",
  "items": [{
    "item_id": "f1", "size_id": "12x16", "finish_id": "natural-oak", "orientation": "portrait",
    "sample_id": "frame-01",
    "position_x_inches": 40, "position_y_inches": 30,
    "photo_width_inches": 12, "photo_height_inches": 16,
    "matting": { "enabled": true, "top_inches": 2, "bottom_inches": 2, "left_inches": 2, "right_inches": 2, "color_id": "museum-white" }
  }],
  "layout_metadata": { "style": "grid", "gap_inches": 3, "gap_unit": "in", "seed": 0, "variant": 0 },
  "preview": { "sofa": true, "index_badges": true, "guides": true }
}
```

**Version rules**:
- **Items**:
  - 1–16 per version, with unique `item_id` values: letters, digits, `_` and `-`, at most 64 characters.
  - `layout_type` is `custom`, `grid`, `salon`, `centre` or `row`; legacy names are normalised.
- **Catalog references**:
  - With `size_id`, the opening must match the catalog size in the given `orientation`.
  - With `finish_id`, the server computes `total_width/height_inches`. A different value from the client returns 422.
  - Without a finish, totals are taken as sent, or opening + mounts.
- **Photos**:
  - `photo_id` must be a photo of the same user (otherwise 403). `photo_id` and `sample_id` are mutually exclusive.
  - When a referenced photo is later deleted, it is reported as `photo_missing: true` on read.
- **Fit**:
  - The layout must fit by the planner's rules (§1.3): margin, minimum bottom or sofa clearance, and no overlaps. Otherwise the response is 422 `VALIDATION_ERROR` with `details[].field = "items.<item_id>"`.
  - `preview.sofa` picks the sofa clearance; when absent, `wall.has_sofa` decides.
- **Metadata**: `layout_metadata` and `preview` accept only the keys shown above (unknown keys → 422). Versions stored earlier may hold other keys.
- **Duplicates**: saving exactly the current version again returns it instead of creating a new number.
- **What a version holds**: the items, layout metadata and preview flags. The **title, wall size and paint** live on the design record (`PATCH /designs/{id}`) and apply to all versions, so changing only those does not create a version.

**Outputs**:
- `Design`: `{ id, user_id, title, description, wall, current_version_id, current_version_number, status, created_at, updated_at }`. `DesignListItem` adds `items_count`.
- `DesignVersionSummary`: `{ version_id, design_id, version_number, layout_type, items_count, bounding_box, created_at }`.
- `DesignDetail.current_version`: `{ id, design_id, version_number, layout_type, template_id, items_count, bounding_box, items[], layout_metadata, preview, created_at }`.
  - Each item adds `frame_id`, `total_*` and `photo_missing`.
  - `matting` includes `color_id` and `color_hex`.

---

## 8. Quotes via WhatsApp (no online pricing)

### 8.1 `POST /quotes/prepare` (bearer; multipart)

Form fields:
- **`file`**: the rendered wall preview (PNG, WebP or JPEG, at most 15 MB, 100–8192 px).
- **`design_data`**: the planner state as a JSON string.

```json
{
  "title": "Living Room Gallery Wall",
  "designId": null,
  "displayUnit": "ft",
  "preview": { "sofa": true },
  "wall": { "widthIn": 144, "heightIn": 108, "paintId": "warm-cream" },
  "layout": { "style": "grid", "gapIn": 3 },
  "frames": [{
    "id": "f1", "sizeId": "12x16", "orientation": "portrait", "finishId": "natural-oak",
    "mount": { "enabled": true, "colourId": "museum-white", "marginIn": 2 },
    "photo": { "kind": "sample", "sampleId": "frame-01" }
  }]
}
```

- **Planner fields**: extra planner fields (`templateId`, `selectedIndex`, …) are ignored. `wall.displayUnit` and `wall.hasSofa` are still accepted from older clients.
- **Validation**:
  - Wall 36–480 × 48–240, 1–16 frames, mount 0–6 in.
  - Catalog IDs for size, finish, mount and paint. Unknown IDs return 422 with `field` like `design_data.frames.0.sizeId`.
  - `photo.kind: "upload"` with a `photoId` must be the user's own photo (403). Session object URLs are ignored.
- **Stored snapshot**: per frame, the opening and outer size (opening + 2 × (mount + finish profile)), the finish label, and the mount colour ID and label.
- **Response**: **201** `{ quote_id: "MQ-2026-0012", status: "draft", whatsapp_url, report_url, expires_at }`.
  - `whatsapp_url` opens WhatsApp with a prefilled message: reference, wall size in the customer's unit (`12 × 9 ft`), arrangement, frame count, finish, report link and contact.
  - `report_url` (`{PUBLIC_APP_URL}/q/{token}`, valid 30 days) is returned **only here**. The server stores a hash of the token.
- **Rate limit**: 10 per user per hour.

### 8.2 Reading quotes

| Endpoint | Auth | Response |
| --- | --- | --- |
| `GET /quotes/{quote_id}` | bearer, owner (else 404) | `{ quote_id, status, design_title, layout_style, wall_size, frame_count, finish_summary, report_url: null, preview_url (signed), customer_name, customer_phone, customer_email, frames: QuoteFrameSummary[], expires_at, created_at }` |
| `GET /quotes/share/{token}` | public (token) | The branded HTML report. With `Accept: application/json`: `{ quote_id, created_at, expires_at, customer_name, customer_contact_masked, design_title, layout_style, wall_dimensions, frame_count, finish_summary, preview_image_url, frames[] }` |
| `GET /quotes/share/{token}/preview` | public (token) | The preview image, with its own type and extension (`moonlight-quote-MQ-….jpg`) |
| `GET /q/{token}` (no `/api/v1`) | public | Redirects to the share report |

- **`QuoteFrameSummary`** (display strings): `{ number, size: "16 × 12 in" (opening as hung), dimensions: "22 × 18 in" (outer), orientation, finish, mount: "Museum White (2 in border)" | "No mount", photo }`.
- **Expired or unknown share tokens** return 404.
- **Report headers**: the report sends its own CSP (no scripts, no third-party requests), `Referrer-Policy: no-referrer` and `Cache-Control: private, no-store`.

---

## 9. Health

| Endpoint | Auth | Response |
| --- | --- | --- |
| `GET /health/live` | public | `{ status, service }` |
| `GET /health/ready` | public | `{ status, service, database: { status, latency_ms }, timestamp }`. Pings MongoDB only |
| `GET /health` | development only; elsewhere `X-Health-Token` (else 404) | Detailed component diagnostics |

## 10. Response headers

- **Every response**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, a deny-all CSP (except `/docs`), `Referrer-Policy` and `Permissions-Policy`.
- **`/auth/*`**: also `Cache-Control: no-store`.
- **Production**: HSTS.
- **CORS**: allows `Authorization`, `Content-Type`, `Accept` and `X-CSRF-Protection` from the configured origins, with credentials.

## 11. Changes from the 2026-11-05 contract

| Area | Before | Now |
| --- | --- | --- |
| IDs | Integer examples (`501`) | ObjectId strings (Q1) |
| Session | Refresh token in the body, no refresh/logout | Cookie-only refresh, `/auth/refresh`, `/auth/logout`, CSRF header (Q2, Q3) |
| Login | `email` only, reduced `user` | `email`, `phone` or `identifier`; full `User` (M1, M5) |
| Password reset, Google | Missing | §2 (M3) |
| Catalog | Colour names only, no sizes | `GET /catalog` with stable IDs; colours `{ id, name, hex, profile_in }` (M8, M9) |
| Templates | `focal_center`, `triptych`, `staircase`; no `row` | `grid`, `salon`, `centre`, `row`; slot `size_id`, `orientation`; `gap_inches` (M6) |
| Geometry | `x_inches`, `margin_inches`/`safe_margin_inches`, `min_x`… boxes, collisions as 422 | `outer_*_inches`, `{ x, y, width, height }` boxes, issues in a 200 `errors[]` (M4, Q10); placeholder frames (M10) |
| Pricing | `POST /pricing/calculate`, GST, shipping | Removed. Quotes are priced by the studio on WhatsApp (Q7, Q8) |
| Designs | Create/get/version only, prices per item | List, PATCH, DELETE; catalog references (`size_id`, `finish_id`, `color_id`, `paint_id`); typed `layout_metadata` and `preview` (M7, M12, Q22) |
| Quotes | `POST /quotes` with shipping address | `POST /quotes/prepare` → WhatsApp link + share report |
| Units | Inches; `mm` | Inches on the wire; `display_unit` adds `m` |
| Photos (Phase 5) | List had thumbnails only; any owner could delete a photo a design used | List adds `preview_url`; `DELETE` is refused with 409 `PHOTO_IN_USE` while a live design uses it |
| Design search (Phase 5) | `search` was passed to MongoDB as a regular expression | Literal, case-insensitive substring match |
