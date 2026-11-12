# Frontend Security

What the frontend already does, and what hosting and the backend must provide.

## In place (frontend)

| Area                    | Measure                                                                                                                                                                                                                                                                                                                                                                                   |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| XSS                     | No `dangerouslySetInnerHTML`, `innerHTML` or `eval` anywhere. All user and API text is rendered through React (auto-escaped). Lint bans `console.log`.                                                                                                                                                                                                                                    |
| Content-Security-Policy | Injected as a `<meta>` tag in production builds (`vite.config.ts` → `contentSecurityPolicy`): `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: <api>; font-src 'self'; connect-src 'self' <api>; object-src 'none'; base-uri 'self'; form-action 'self'`. The API origin is added automatically when `VITE_API_BASE_URL` is absolute. |
| Third parties           | None at runtime. Fonts are self-hosted (`@fontsource`), with no Google Fonts requests and no IP leakage to third parties.                                                                                                                                                                                                                                                                 |
| URLs from the API       | `resolveApiUrl()` passes only http(s), protocol-relative, `blob:` and `data:image/…`. `javascript:` / `data:text/html` become harmless same-origin paths.                                                                                                                                                                                                                                 |
| Tokens                  | Access token in memory only (`services/tokenStorage.ts`); the refresh token is an httpOnly cookie that JavaScript never sees. Legacy localStorage tokens are deleted on load. A garbled `expires_in` counts as expired. Tokens are never logged.                                                                                                                                         |
| Email format            | Strict practical pattern (`identifier.ts`): no markup or quotes, no leading, trailing or double dots, valid hostname labels, alphabetic TLD, local part ≤ 64. ASCII only.                                                                                                                                                                                                                 |
| Input                   | Client-side validation plus `maxLength` caps (identifier 254, password 128). The server must still validate everything. Client checks are for UX only.                                                                                                                                                                                                                                    |
| Error messages          | Sign-in failures are generic ("details don't match"), never "no account with this email". 5xx bodies and exception text are never shown to the user. Route error details are logged only in development.                                                                                                                                                                                  |
| Stored designs          | Saved designs (mock `localStorage` now, `/designs` API later) are untrusted: `sanitizePlannerState()` rebuilds every field, maps unknown ids to defaults, clamps numbers to the planner rules, caps frames at 16 and the list at 50, and **never restores photo URLs** (only known bundled samples). Titles render as text.                                                               |
| Uploads & export        | Photos are checked for MIME type, size (≤ 25 MB) and minimum resolution, then used as session `blob:` URLs. The PNG export embeds images via `<img>` and canvas (`img-src`), not `fetch()`, so `connect-src` stays `'self' <api>` with no `blob:`.                                                                                                                                        |
| Secrets                 | None in the repo. `.env*` files are git-ignored except `.env.example`. Only `VITE_*` vars reach the bundle and they're public by design. `API_PROXY_TARGET` (dev only) has no `VITE_` prefix, so it can't leak.                                                                                                                                                                           |
| Source maps             | Not emitted in production builds (Vite default).                                                                                                                                                                                                                                                                                                                                          |
| Dependencies            | `npm audit`: 0 vulnerabilities (2026-11-05).                                                                                                                                                                                                                                                                                                                                              |

## Required from hosting (can't be done in the frontend)

Send these as **HTTP response headers** for `index.html` and assets:

```
Content-Security-Policy: frame-ancestors 'none'     # clickjacking (not supported in <meta>)
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Cache-Control: no-cache                              # index.html only
Cache-Control: public, max-age=31536000, immutable   # /assets/* (content-hashed)
```

Also configure an SPA fallback, so unknown paths serve `index.html` with status 200 and the app shows its own 404.

When Google sign-in lands (Phase 5), add `https://accounts.google.com` to `script-src`,
`frame-src` and `connect-src` in the CSP plugin.

## Provided by the backend (Phase 2, 2026-11-12)

See [backend/README.md → Security model](../backend/README.md#security-model-phase-2). Items that
used to be requests (API_ALIGNMENT Q2, Q3, Q17, Q18) are done:

- **Q3:** the refresh token is an httpOnly, SameSite cookie and never reaches JavaScript. The access
  token lives in memory only (`services/tokenStorage.ts`), and tokens persisted by older builds are
  deleted on load.
- **Q2:** refresh (atomic rotation, concurrent-tab safe, reuse detection) and logout (server-side
  revocation).
- **Q17:** layered login rate limits with `Retry-After`; identical `401` and timing for unknown
  accounts.
- **Q18:** server-side input and body-size limits; no internals in error messages.
- **CSRF:** `apiClient` sends `X-CSRF-Protection: 1` on every non-GET request. The cookie
  endpoints reject requests without it, or from an `Origin` outside `CORS_ORIGINS`.

When Phase 5 wires auth: on app start call `POST /auth/refresh` (cookie sent automatically) to restore
the session; on a `401` from it, treat the user as signed out.
