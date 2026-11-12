# Frontend Roadmap

## Phase 0: Setup & documentation ✅

- [x] Analyse `reference_designs/` and extract design direction and tokens
- [x] Vite + React 19 + TypeScript + Tailwind v4 project in `frontend/`
- [x] Design tokens, fonts, base styles, global focus/reduced-motion
- [x] `@/` alias, `cn()`, typed env, API client, dev proxy, lazy routes with placeholders
- [x] oxlint + Prettier, `.editorconfig`, `.gitignore`, `.env.example`, docs

## Phase 1: Folder structure, assets & API contract ✅ (2026-11-05)

- [x] Final folder structure with dependency rules (ARCHITECTURE.md)
- [x] Assets verified against designs: inventory, verdicts, workarounds W1–W5 (ASSETS.md)
- [x] Asset manifests (`src/assets/{brand,auth,memoryWall}.ts`, split per area in Phase 2) + `vite-imagetools` (WebP/srcset; sample PNGs 2.4 MB → ≤66 KB)
- [x] Missing assets covered: Google "G" icon, `lucide-react`, temporary favicon, swatch colours
- [x] `hero-fits` Tailwind variant so the baked-in hero taglines are never cropped
- [x] Backend contract stored verbatim (API_CONTRACT.md). TS types in `src/types/api/`
- [x] `apiClient` aligned: `/api/v1`, Bearer auth, error envelope → `ApiError`, query, upload, 401 hook
- [x] `endpoints.ts`, `tokenStorage.ts`, `lib/units.ts`, `lib/money.ts`
- [x] Mismatches & questions for backend (API_ALIGNMENT.md: M1–M12, Q1–Q16)
- [ ] **Waiting on designer:** vector logo, text-free heroes, empty room + sofa cut-out (ASSETS.md)
- [ ] **Waiting on backend:** 🔴 items in API_ALIGNMENT.md

## Phase 2: Login page ✅ (2026-11-05)

- [x] Shared UI: `Button`, `TextField`, `PasswordField`, `Divider`, `TextLink` (components/ui);
      `Logo`, `EstablishedTag` (components/brand); `Alert`, `Spinner` (components/feedback)
- [x] Auth shell shared with Register: `AuthLayout`, `AuthHero`, `AuthDecorations` (login + register
      placements), `AuthHeader`, `AuthSwitchPrompt`, `GoogleButton`
- [x] `LoginForm` + `useLoginForm`: single "Mobile No. or Email" field → `{ email }` or `{ phone }` (E.164),
      blur/submit validation, focus-first-invalid, API error → field mapping ready for Phase 5
- [x] Placeholders (replaced in Phase 4): Google, `/forgot-password`, mock submit
- [x] `short` height variant + `useMediaQuery`; autofill styling
- [x] Verified in Edge at 320×640, 390×844, 844×390, 768×1024, 1024×768, 1280×720, 1366×768,
      1440×900, 1920×1080, 2560×1440: no horizontal scroll, no overflow on laptops, no console errors

## Audit after Phase 2 ✅ (2026-11-05)

- [x] Bugs: autofill race / stale state, double-submit race, API-error focus, misleading error
      copy (429/5xx), lost aria-describedby, `.env.local` proxy setting ignored, stale page titles,
      tampered-storage + NaN-expiry token handling, abort-listener leak, missing error boundary
- [x] Security: production CSP, self-hosted fonts (no third parties), `resolveApiUrl` allow-list,
      input `maxLength`, generic credential errors, no internals in UI (docs/SECURITY.md)
- [x] Accessibility: contrast fixes (field borders, EST text, placeholders), toggle semantics,
      "OR" divider readable, `required` exposed, ≥ 24px targets, jsx-a11y lint
- [x] Performance: stable vendor chunks, unused font weights dropped, `useMediaQuery` caching,
      delayed loader (no flash)
- [x] Quality: generic `hooks/useForm`, `GoogleSignIn`, `pageTitle()`, strict TS +
      `noUncheckedIndexedAccess`, Vitest (70 tests), `npm run check` gate

## Phase 3: Register page ✅ (2026-11-05)

- [x] `RegisterPage` on the shared auth shell (`AuthLayout variant="register" compact`, `AuthHeader
align="center" titleTone="brand" compact`), register ornaments, register hero
- [x] Fields: **Full Name** (added for the backend's `full_name`; first, same field style), Email,
      Mobile (`PhoneField` with fixed `+91`), Password (+ policy hint)
- [x] `useRegisterForm` on `hooks/useForm`; `registerValidation` (Unicode names, Indian mobile
      normalisation → E.164, assumed password policy); shared `mapAuthError` (login + register; 409 copy)
- [x] UI only (wired to the API in Phase 4)
- [x] New reusable pieces: `PhoneField`, `Button variant="primary-gradient"`, `AuthHeader compact`
- [x] Verified: 110 unit tests, 28 register browser checks, login regression (23), no overflow on
      70 page loads (320 → 2560px). Fits without scrolling at 1440×900+; scrolls ~70–140px on
      768/720-high laptops (4 fields + hint, sticky hero), as expected on phones

## Audit after Phase 3 ✅ (2026-11-05)

- [x] Bug/security: email validation accepted `a@b..co`, `.a@b.com`, `a@-b.com` and
      `"><script>@x.com` (login + register). Now a strict practical pattern + 64-char local part
- [x] Bug: phone `maxLength` 16 truncated formatted input like `+91 (98765) 43210` → 20
- [x] A11y: no input focus indicator in Windows High Contrast (box-shadow ring) → forced-colors outline
- [x] UX: browser spellcheck no longer underlines names in Full Name
- [x] Duplication: shared `AuthForm` skeleton (Login/Register now only declare fields);
      `AUTH_LIMITS` single source for input limits
- [x] Tests: React Testing Library + jsdom. `useForm` behaviour (autofill batching, single
      submission, unmount abort, focus management) and Login/Register integration are now in
      `npm run check` (137 tests)
- [x] Verified: 0 dev-mode React warnings; 28 register + 23 login browser checks; forced-colors
      check; no overflow on 70 page loads; login fits all laptops, register fits ≥ 900px-tall laptops

## Phase 4: Memory Wall Planner ✅ (2026-11-05)

- [x] **Geometry engine** (`features/memory-wall/lib/geometry/`, pure TS, unit-tested): four layout
      algorithms (grid, row, centre, salon) → placement (centred, eye level 60″, sofa clearance,
      margins) → validation (too wide/tall, overlap, coverage). Every input change recalculates.
- [x] Planner UI matching the mockup: Wall Configuration, Layout (+ number of frames), AI Layout
      Assistant presets, live canvas (drawn to scale incl. the 84″ sofa), Frame & Photo Selection,
      Preview Settings, option carousel, Regenerate / Redesign / Generate Layout
- [x] Popups: Preview Fullscreen (gallery stage + **Download PNG** moved here), All Templates (live
      previews on the user's wall + fit badge), My Saved Templates (mock store, search, open, delete),
      Save design
- [x] Session photo upload with DPI quality hint and orientation suggestion; Undo toasts for
      destructive actions; responsive 3-col → 2-col → stacked with a fixed mobile action bar
- [x] Verified: 163 unit/component tests (incl. a 1,536-layout invariant sweep), 51 browser checks on
      prod + dev builds, no overflow 320 → 1920px, 0 console errors/warnings

## Audit after Phase 4 ✅ (2026-11-05)

- [x] Bug (prod only): **Download failed whenever an uploaded photo was on the wall**. The CSP blocks
      `fetch(blob:)`. Export now embeds images via `<img>` + canvas (also caps 25 MB uploads at export size)
- [x] Bug: collapsing "Frame & Photo Selection" on phones **revoked every uploaded photo** (upload hook
      lived in the panel). Moved to page level; uploads target frames by id, so late uploads can't land on
      the wrong frame
- [x] Bug: Download success/error toasts rendered **behind the fullscreen modal**. Status now lives in the
      dialog ("Downloaded" / "Try again" + live region)
- [x] Bug: Generate Layout double-click → two timers/toasts, and edits during the delay were lost on Undo.
      Bug: drag-selecting text in a dialog field and releasing on the backdrop closed the dialog
- [x] Bug: NaN frame count/variant corrupted state. Template fit badges ignored the sofa and said
      "Needs ≥ X wide" for too-tall layouts. Dimension error text kept the old unit
- [x] Security: saved designs fully sanitised (`sanitizePlannerState`), upload/remote URLs never restored,
      store capped at 50, cross-tab sync. Sign out clears the token store
- [x] A11y: toasts pause on hover/focus, 8 s for Undo toasts (WCAG 2.2.1). Focus is kept on delete /
      keep / after delete in Saved designs, and on stepper buttons at their bounds
- [x] UX consistency: AI preset buttons now offer Undo like the Templates dialog (one shared handler)
- [x] Performance: scene memoised on geometry inputs only (`SceneInput`). Selecting frames and toggling
      guides, badges or units no longer rebuilds the layout. Stable `onSelect` lets the memoised SVG skip
      renders
- [x] Verified: 176 tests (+13), 20 new audit + 51 planner browser checks on prod and dev (0 warnings),
      login 23 / register 28, no overflow on 70 page loads

## Auth responsive pass ✅ (2026-11-07)

- [x] Audit ([AUTH_RESPONSIVE_AUDIT.md](AUTH_RESPONSIVE_AUDIT.md)). The reference shots are the current UI at 80 % (register)
      and 90 % (login) zoom on a 1536×735 browser viewport. Earlier "fits" checks used whole-screen sizes.
- [x] Height-aware density: `auth-fluid` variant + `.auth-scope` custom properties (index.css). Fluid gaps,
      logo, title and controls. Rem-stepped text with floors (13 / 14 / 12px, 40px controls, 44px and 16px on touch)
- [x] Removed the 80px wave clearance on short screens. Ornaments scale with height instead
- [x] `TextField` / `Button lg` read optional `--field-*` / `--button-lg-*` (defaults unchanged, Memory Wall
      verified identical). The password toggle fits 40px fields
- [x] Phones: compact portrait rhythm, safe-area padding, `viewport-fit=cover` scoped to auth pages
      (`useViewportFitCover`)
- [x] Verified: 0 overflow on both pages at 1280×585 → 2560×1440, 1024×768, 768×1024, 430×932, 390×844.
      Interactions, tab order, 200 % zoom and 20px root font checked. `npm run check` + `npm run build` green

## Memory Wall redesign: "Gallery Atelier" ✅ (2026-11-07)

- [x] Audit + plan: [MEMORY_WALL_REDESIGN_AUDIT.md](MEMORY_WALL_REDESIGN_AUDIT.md)
- [x] Fixed-height studio shell, three layout modes (desktop / split / stacked) and three height tiers.
      No page scroll from 2560×1440 down to 1280×600, on tablets, phones and landscape phones
- [x] Stage: dark lit backdrop and the wall fitted on both axes. Toolbar: layout style, view toggles,
      fullscreen and a ⋯ menu (view, Download PNG, Reset). The Generate cluster sits in the footer
- [x] Carousel arrows/dots removed (main + fullscreen, incl. the ←/→ keys). Generate Layout is a
      single button (the Variations split menu was later removed; variants stay internal to Generate)
- [x] Header: project title, fit chip with warnings + quick fixes, Templates, My Designs, Save and a
      charcoal Request a Quote. "My Saved Templates" renamed **My Designs** (copy only, same store)
- [x] Inspector: ‹ › + thumbnail navigator, Photo / Frame / Mount tabs, Apply to all with confirmation
- [x] Room: new floor strip, 84″ sofa, lamp and plant cut-outs drawn to scale (W4), included in exports.
      New 4:3 AI thumbnails, three landscape samples, crescent logo mark
- [x] New primitives: `Menu`, `Tabs`, `Tooltip`; planner sizes on the existing ones (defaults unchanged)
- [x] Verified: `npm run check` green (182 tests, +6 room tests), 11 viewports with 0 page overflow,
      52 desktop + 9 phone workflow checks in Edge, 0 console errors

## Phase 5: Live API wiring

`services/<domain>.ts` modules, auth provider + protected routes, React Query, and replacing
local fallbacks with live endpoints as the backend resolves API_ALIGNMENT items.

---

# Backend Roadmap

`backend/` started as a copy of the SAF Studio FastAPI backend. Details: [backend/README.md](../backend/README.md).

## Backend Phase 1: Separate from SAF Studio ✅ (2026-11-12)

- [x] `uv sync` fixed (application mode, OneDrive copy link-mode, undeclared runtime deps); lock verified
- [x] SAF credentials removed from `backend/.env`; Moonlight development config with generated secrets,
      local MongoDB `moonlight_studio`, offline integrations; documented `.env.example`
- [x] Production configuration guard (secrets, DEBUG, R2, Resend, WhatsApp number, https URL); errors
      never echo values
- [x] Rebrand to Moonlight Photo Studio: API metadata, logs, OTP email, WhatsApp message, quote report,
      file names, `MQ-` quote references, seeder, scripts, tests, README
- [x] `STORAGE_BACKEND=local`: confined, atomic file storage with HMAC-signed expiring downloads; R2 unchanged
- [x] Fixes: Google sign-in fails closed without `GOOGLE_CLIENT_ID` (was: any audience accepted); Resend
      test-mode errors no longer reveal the test inbox
- [x] Hermetic tests (no `.env`, network blocked); 38 → 0 Ruff issues; dead code removed; 264 tests

## Backend Phase 2: Security hardening ✅ (2026-11-12)

- [x] Client IP only from TRUSTED_PROXIES (right-to-left X-Forwarded-For); run uvicorn with
      `--no-proxy-headers`
- [x] Shared rate limiter (MongoDB TTL collection, atomic, hashed keys; bounded memory fallback):
      login per IP + account / account / IP, OTP request + verify, reset step, uploads, quotes;
      `Retry-After`
- [x] Real dummy Argon2id hash; forgot-password email sent in the background (no timing or error leak)
- [x] Atomic refresh rotation with concurrent-tab grace and family revocation on reuse
- [x] Refresh token cookie-only (configurable path); CSRF header + Origin check on cookie endpoints;
      frontend access token in memory only
- [x] Sub-second `iat`; optional auth now honours password-change revocation
- [x] Streaming body limits (413 before buffering) + upload size checks before `read()`
- [x] Minimal public `/health/live` and `/health/ready`; token-guarded detailed `/health`
- [x] No exception, driver or input text in API errors; JSON log formatter fixed and masked
- [x] Security headers, tighter CORS, private caching for share links; RFC 9110 status constants
- [x] 324 backend tests (+60 security, incl. live-MongoDB concurrency), mutation-checked; 40/40
      end-to-end checks on a throwaway database

## Backend Phase 3: Contract alignment & data consistency ✅ (2026-11-12)

- [x] Backend planner catalog (`app/modules/catalog.py`, `GET /catalog`) is the source of truth:
      frame sizes, wood finishes, mount colours, paint shades, layout styles, templates and rules,
      with stable IDs; the frontend constants are checked against it by a contract test
- [x] Seeder: moulding colours carry finish IDs, Triptych is a `row` template, templates store
      their gap; legacy categories and colour documents are normalised on read (no migration)
- [x] Validation matches the planner: wall 36–480 × 48–240, 1–16 frames, gap 0–12, mount 0–6,
      `display_unit` `m`, catalog IDs enforced, fit = 6 in margin + 12 in floor (or sofa line)
- [x] Server-computed outer frame sizes (opening + mounts + moulding face), typed version
      metadata/preview, duplicate-version check covers every stored field
- [x] Quotes: catalog sizes/finishes/mount labels (no SAF tables, no silent 12 × 16 fallback),
      planner-state fields (top-level unit, sofa, paint), JPEG/WebP previews keep their extension,
      wall sizes in the customer's unit, no broken owner report link
- [x] Share report and reset email restyled to the Moonlight palette; no Google Fonts
- [x] `API_CONTRACT.md` regenerated from the implementation; `types/api/*` and `endpoints.ts`
      aligned (string IDs, real shapes, no pricing); full validation field paths
- [x] Design list `sort` allowlisted; PyMongo's DEBUG command log (whole documents) disabled
- [x] 377 backend tests (+52 contract/regression), mutation-checked; 47/47 end-to-end checks
      (plus the Phase 2 smoke, 40/40) on a throwaway local database

## Frontend Phase 4: Authentication integration ✅ (2026-11-12)

- [x] `AuthProvider` + `useAuth()`: session restore on load (refresh cookie → `/auth/me`), login,
      register, Google, logout; `ProtectedRoute` / `GuestRoute`; post-login return to the page the
      visitor came from (validated, no open redirect); "session ended" / "server unreachable" notices
- [x] `apiClient`: single-flight refresh, replay once on 401, proactive renewal of an expired token;
      CSRF header and cookie credentials preserved; `services/authService.ts` for the endpoints
- [x] Login and Register on the real API (mock layer deleted); duplicate-account, validation,
      rate-limit (429), disabled-account, network and 5xx errors mapped to safe messages
- [x] Google Identity Services button on Login and Register → `POST /auth/google`; honest fallback
      when no client ID is configured or the script is blocked; production CSP opens only Google's
      `gsi` paths when a client ID is set
- [x] Forgot password: email → 6-digit code (resend cooldown from the server, attempts-left feedback)
      → new password → sign in with a success notice; nothing stored client-side
- [x] Planner header shows the signed-in user; Sign out revokes server-side (and reports a failure)
- [x] Backend security fix: a rotated refresh cookie could mint an access token inside its 30 s grace
      even after logout or a password reset
- [x] Frontend tests 181 → 256 (auth UI, session, refresh concurrency, Google, reset flow), backend
      377 → 379; 49/49 real-browser checks and 38/38 HTTP security checks against a throwaway local
      database

## Next: frontend Phase 5 (planner API integration)

Phase 5 loads `GET /catalog`, saves designs through `/designs` (blocking Save while the layout doesn't
fit), uploads photos and sends quotes through `/quotes/prepare`.
