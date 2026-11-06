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
- [x] Placeholders: Google (inline "coming soon"), `/forgot-password` page; mock submit → `/memory-wall`
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
- [x] UI only: mock submit → `/memory-wall`; Google button shows "coming soon"
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
