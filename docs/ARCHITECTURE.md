# Frontend Architecture

## Stack choices

| Concern     | Choice                                                                          | Why                                                                                                      |
| ----------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Build       | Vite 8                                                                          | Fast HMR, native ESM, built-in code splitting                                                            |
| UI          | React 19 + TypeScript (strict)                                                  | Team requirement                                                                                         |
| Styling     | Tailwind CSS v4 (`@tailwindcss/vite`)                                           | CSS-first `@theme` tokens, no config file, tiny CSS output                                               |
| Routing     | React Router 7                                                                  | Route-level lazy loading                                                                                 |
| Class utils | `clsx` + `tailwind-merge` → `cn()`                                              | Safe className overrides on reusable components                                                          |
| Icons       | `lucide-react`                                                                  | Thin outline set matching the mockups; tree-shaken per icon                                              |
| Images      | `vite-imagetools` (dev dep)                                                     | Build-time resize + WebP re-encode and `srcset` from query params                                        |
| Lint/format | oxlint (+ jsx-a11y, import, vitest plugins) + Prettier (Tailwind class sorting) | Fast; a11y + import-cycle checks                                                                         |
| Tests       | Vitest + React Testing Library                                                  | `*.test.ts` (node) for pure logic; `*.test.tsx` with `// @vitest-environment jsdom` for hooks/components |
| Fonts       | `@fontsource` (self-hosted)                                                     | No third-party requests; CSP stays `font-src 'self'`                                                     |

Add when the phase needs them:

- `react-hook-form` + `zod`: only if forms outgrow `hooks/useForm` (multi-step, arrays)
- `@tanstack/react-query` (server state, Phase 5)

## Folder structure

Organised by feature, with a thin shared layer. Folders marked _(empty)_ hold a `.gitkeep`
until their phase fills them.

```
frontend/src/
├── app/                         App shell
│   ├── App.tsx
│   ├── router.tsx               All routes, lazy-loaded
│   ├── NotFoundPage.tsx
│   └── providers/               (empty) QueryClientProvider… (Phase 5). AuthProvider lives in features/auth
│
├── assets/                      Static files. See docs/ASSETS.md
│   ├── types.ts                 ImageAsset, HeroImageAsset, SamplePhotoAsset
│   ├── brand.ts  auth.ts  memoryWall.ts   ★ Asset manifests, one per area (the ONLY importers
│   │                            of image files). Split so each page bundles only its own assets
│   ├── icons/                   google-g.svg
│   └── images/                  logo.svg, login/, register/, memory_wall/{frames,layouts}
│
├── components/                  Shared, feature-agnostic UI (no API calls, no feature imports)
│   ├── ui/                      Button, TextField, PasswordField, Divider, TextLink (next: IconButton,
│   │                            Divider, SegmentedControl, Toggle, NumberStepper, Select,
│   │                            SwatchPicker, Badge, Card…
│   ├── brand/                   Logo, EstablishedTag ("— EST. 1985 —")
│   ├── feedback/                Alert, Spinner (next: Skeleton, Toast)
│   └── layout/                  PageLoader, PlaceholderPage (temporary)
│
├── config/
│   ├── env.ts                   Typed VITE_* vars
│   └── routes.ts                Path constants (never hard-code a URL path)
│
├── features/                    One folder per product area
│   ├── auth/
│   │   ├── components/          (empty) AuthLayout, AuthHero, LoginForm, RegisterForm, GoogleButton
│   │   ├── hooks/               useLoginForm, useRegisterForm (next: useSession)
│   │   └── pages/               LoginPage, RegisterPage
│   ├── memory-wall/
│   │   ├── components/          (empty) PlannerHeader, WallConfigPanel, LayoutPanel,
│   │   │                        AiLayoutAssistant, LayoutCanvas, FrameSelectionPanel,
│   │   │                        PreviewSettingsPanel, ActionBar
│   │   ├── hooks/               (empty) useWallPlanner (single reducer for planner state)
│   │   ├── lib/                 (empty) Pure planner maths: client layouts, UI ↔ API mappers
│   │   ├── pages/               MemoryWallPage
│   │   └── constants.ts         Swatches, units, defaults, layout-style ↔ API mapping
│   └── quotes/                  (empty) Request-a-quote form, "My quotes" list
│       ├── components/
│       └── pages/
│
├── hooks/                       useForm (generic form state), useMediaQuery
├── lib/                         Pure, framework-free helpers
│   ├── cn.ts
│   ├── units.ts                 ft/in/cm/m ↔ inches (API is inches-only)
│   └── money.ts                 formatMoney(DecimalString, currency)
│
├── services/                    The only layer that talks to the network
│   ├── apiClient.ts             fetch wrapper: base URL, Bearer auth, single-flight refresh, ApiError
│   ├── endpoints.ts             Every backend path from API_CONTRACT.md
│   ├── authService.ts           Typed auth endpoints (register, login, Google, refresh, reset…)
│   └── tokenStorage.ts          Access token in memory (refresh token is an httpOnly cookie)
│                                Phase 5 adds one module per domain: catalog.ts, photos.ts,
│                                templates.ts, geometry.ts, designs.ts, quotes.ts
│
├── styles/theme.css             Design tokens (@theme)
├── types/
│   └── api/                     ★ TypeScript mirror of API_CONTRACT.md, one file per section
│       ├── common.ts            EntityId (string), ListResponse<T>, ApiErrorEnvelope, BoundingBox…
│       ├── auth.ts  catalog.ts  photos.ts  templates.ts
│       ├── geometry.ts  designs.ts  quotes.ts
│       └── index.ts             `import type { User } from '@/types/api'`
├── index.css                    Tailwind entry, custom variants, base layer
├── main.tsx
└── vite-env.d.ts                Env + imagetools import typings
```

### Dependency rules

```
app ──► features ──► components, hooks, lib, services, config, assets, types
                     services ──► config, types
                     components ──► lib, assets, types   (never features, never services)
```

- **Features don't import each other.** If two features need something, move it down
  (`components/`, `lib/`, `services/`). This is why domain API modules live in `services/`
  rather than inside a feature. For example, memory-wall's "Request a Quote" and the quotes
  feature both use `services/quotes.ts`.
- **Only `services/` calls `fetch`.** Only the `assets/*.ts` manifests import image files.
- **API types stay snake_case**, exactly as on the wire. Map them to UI state in
  `features/*/lib/` mappers. Don't rename fields inside `types/api/`.
- Use the `@/` alias for anything outside the current folder.

### Where does new code go?

| You're adding…                         | Put it in                                                                                 |
| -------------------------------------- | ----------------------------------------------------------------------------------------- |
| A generic control used on 2+ screens   | `components/ui/`                                                                          |
| A piece of one screen                  | `features/<feature>/components/`                                                          |
| State or a side effect for one feature | `features/<feature>/hooks/`                                                               |
| Pure maths/formatting with no React    | `lib/` (shared) or `features/<feature>/lib/`                                              |
| A backend call                         | `services/<domain>.ts` using `api` + `endpoints`                                          |
| A type from the backend                | `types/api/<section>.ts`                                                                  |
| A type only the UI uses                | Next to the code that uses it                                                             |
| An image/SVG                           | `assets/images/<screen>/`, then register it in that area's manifest (`assets/auth.ts`, …) |

## Component conventions

1. **One component per file**, PascalCase filename = component name. Named exports for
   components; default export only for lazy-loaded pages.
2. **Extend native props** so components behave like the element they wrap:
   ```tsx
   interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
     variant?: "primary" | "secondary" | "ghost" | "link";
     size?: "sm" | "md" | "lg";
     loading?: boolean;
   }
   ```
   React 19 passes `ref` as a normal prop, so `forwardRef` isn't needed.
3. **Always accept `className`** and merge it last with `cn()`.
4. **Variants via lookup objects**, not nested ternaries.
5. **Mobile-first classes:** base classes target phones, then layer `sm: md: lg: xl:`.
6. **No business logic in `components/`.** API calls and state machines live in feature hooks.
7. **Accessibility is part of "done"**: label every control, keyboard-operable, visible focus.

## Performance rules

- Pages are `lazy()`-loaded in `app/router.tsx`. Every new route follows this pattern.
- Images come from the area manifests (`@/assets/auth`, `@/assets/memoryWall`, `@/assets/brand`), which provides `src`, `srcSet`, `width`, `height` and `alt`. Always
  pass `width`/`height`. Use `loading="lazy"` below the fold and `fetchPriority="high"` only on
  the auth hero.
- The auth hero renders only under the `hero-fits` variant (RESPONSIVE.md). Don't mount the
  `<img>` otherwise.
- Memoise only where profiling shows a need (likely the planner canvas).
- Import icons individually: `import { Lock } from 'lucide-react'`.

## Backend integration

The contract lives in [API_CONTRACT.md](API_CONTRACT.md). Gaps and open questions are in
[API_ALIGNMENT.md](API_ALIGNMENT.md).

- **Base URL** `/api/v1` (`VITE_API_BASE_URL`). In dev, Vite proxies `/api` and `/static` to
  `VITE_API_PROXY_TARGET` (default `http://localhost:8000`), so there's no CORS locally.
- **Auth:** JWT Bearer. `apiClient` attaches `Authorization: Bearer …` from `tokenStorage`.
  On a 401 for a signed-in user it renews the token through the refresh cookie (one shared
  `/auth/refresh`) and replays the request once; if that fails it clears tokens and calls the handler
  registered with `setUnauthorizedHandler` (`AuthProvider` sets it; the route guards then redirect).
  `features/auth/AuthProvider` owns the user and session state; `useAuth()` exposes it.
- **Errors:** every failure throws `ApiError` with `{ status, code, message, details[], timestamp }`
  from the contract's envelope. `error.fieldErrors` gives `{ field: issue }` for inline form
  errors. Network failures use `code: 'NETWORK_ERROR'` and `status: 0`.
- **Usage pattern** (Phase 5):
  ```ts
  // services/templates.ts
  export const listTemplates = (query?: TemplatesQuery, signal?: AbortSignal) =>
    api.get<ListResponse<LayoutTemplate>>(endpoints.templates.list, {
      query: { ...query },
      signal,
    });
  ```
- **Units & money:** convert to inches with `lib/units.ts` before sending. Show money with
  `formatMoney()` and never do arithmetic on prices client-side.
- **URLs from the API** (`thumbnail_url`, `/static/...`): always pass them through `resolveApiUrl()`.

## Memory Wall Planner

Pipeline (all pure functions, `features/memory-wall/lib/`):

```
PlannerState ──reducer (plannerState.ts)──► PlannerState
      │
      ▼ buildScene (geometry/scene.ts)
frame configs → outer sizes (opening + mat + moulding)
  → layout algorithm (geometry/layouts.ts: grid | row | centre | salon; seed + variant)
  → placement on the wall (centred, eye level, above sofa, margins)
  → validation (fits / overlap / coverage)  ─►  Scene  ─►  WallSvg (one renderer for canvas,
                                                          fullscreen, thumbnails and PNG export)
```

- Units: everything internal is **inches** (API convention); display units only at the edges.
- Determinism: `(seed, variant)` fully determines an arrangement, so saved designs reopen
  identically. Seed 0 = canonical; "Regenerate" picks a new seed; the carousel picks the variant.
- "Generate Layout" scores every style × variant (fits → ~25% coverage → aspect) and applies the best.
- Mock seams for Phase 5: `savedDesigns.ts` (→ /designs), `templates.ts` (→ /templates),
  `usePhotoUpload` (→ /photos/upload). The scene's warnings mirror /geometry/validate-layout.

## Forms

Auth screens compose `features/auth/components/AuthForm` (error alert → fields → CTA → "OR" →
Google) and only declare their fields. Input limits come from `features/auth/lib/limits.ts`
(`AUTH_LIMITS`); never hard-code a `maxLength`.

Use `hooks/useForm` for every text form. A feature provides only:

- `fields` (in visual order), `initialValues`, `validateField(field, value, values)`;
- `onSubmit(values, signal)`, which does the work and throws on failure;
- `mapSubmitError(error)`, which turns an `ApiError` into `{ fieldErrors, formError }`.

The hook handles blur/submit validation, live re-validation, focusing the first invalid field,
a one-submission-at-a-time guard, aborting on unmount, and autofill-safe state. See
`features/auth/hooks/useLoginForm.ts` (about 20 lines) as the template.

## Quality gate

`npm run check` = typecheck + lint + unit tests + format check. Run it before every commit/PR.
Every page sets a document title via `<title>{pageTitle('…')}</title>` (`config/app.ts`).
Routes are wrapped in one error boundary (`app/RouteErrorPage.tsx`), which also handles failed
lazy-chunk loads after a deploy.

## Environment variables

See [`frontend/.env.example`](../frontend/.env.example). Only `VITE_*` vars reach the browser,
and they are **public**. Never put secrets in them. Typed access is via `@/config/env`.
