# Frontend Security

What the frontend already does, and what hosting and the backend must provide.

## In place (frontend)

| Area                    | Measure                                                                                                                                                                                                                                                                                                                                                                                   |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| XSS                     | No `dangerouslySetInnerHTML`, `innerHTML` or `eval` anywhere. All user and API text is rendered through React (auto-escaped). Lint bans `console.log`.                                                                                                                                                                                                                                    |
| Content-Security-Policy | Injected as a `<meta>` tag in production builds (`vite.config.ts` → `contentSecurityPolicy`): `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: <api>; font-src 'self'; connect-src 'self' <api>; object-src 'none'; base-uri 'self'; form-action 'self'`. The API origin is added automatically when `VITE_API_BASE_URL` is absolute. |
| Third parties           | None at runtime. Fonts are self-hosted (`@fontsource`), with no Google Fonts requests and no IP leakage to third parties.                                                                                                                                                                                                                                                                 |
| URLs from the API       | `resolveApiUrl()` passes only http(s), protocol-relative, `blob:` and `data:image/…`. `javascript:` / `data:text/html` become harmless same-origin paths.                                                                                                                                                                                                                                 |
| Tokens                  | Access token in memory only (`services/tokenStorage.ts`); the refresh token is an httpOnly cookie that JavaScript never sees. Legacy localStorage tokens are deleted on load. A garbled `expires_in` counts as expired. Tokens are never logged.                                                                                                                                          |
| Email format            | Strict practical pattern (`identifier.ts`): no markup or quotes, no leading, trailing or double dots, valid hostname labels, alphabetic TLD, local part ≤ 64. ASCII only.                                                                                                                                                                                                                 |
| Input                   | Client-side validation plus `maxLength` caps (identifier 254, password 128). The server must still validate everything. Client checks are for UX only.                                                                                                                                                                                                                                    |
| Error messages          | Sign-in failures are generic ("details don't match"), never "no account with this email". 5xx bodies and exception text are never shown to the user. Route error details are logged only in development.                                                                                                                                                                                  |
| Stored designs          | Saved designs (mock `localStorage` now, `/designs` API later) are untrusted: `sanitizePlannerState()` rebuilds every field, maps unknown ids to defaults, clamps numbers to the planner rules, caps frames at 16 and the list at 50, and **never restores photo URLs** (only known bundled samples). Titles render as text.                                                               |
| Uploads & export        | Photos are checked for MIME type, size (≤ 2 MB after automatic shrinking) and minimum resolution, then uploaded to the API. The PNG export embeds images via `<img>` and canvas (`img-src`), not `fetch()`, so `connect-src` stays `'self' <api>` with no `blob:`.                                                                                                                                        |
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

**Google sign-in (Phase 4).** When `VITE_GOOGLE_CLIENT_ID` is set at build time, the CSP plugin adds
exactly what Google Identity Services needs: `script-src https://accounts.google.com/gsi/client`,
`style-src …/gsi/style`, `connect-src …/gsi/` and `frame-src …/gsi/`. Nothing else is opened, and
without a client ID the CSP is unchanged. The Google popup also needs the host to send
`Cross-Origin-Opener-Policy: same-origin-allow-popups` (a stricter `same-origin` breaks the popup).
Add the production origin to the client's _Authorized JavaScript origins_ in Google Cloud Console.

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

## Free-tier safeguards and resource abuse (Phase 7, 2026-11-12)

- **Email allowance (Resend, 100 per UTC day).** One shared counter in MongoDB (`usage_counters`,
  key `email:<UTC date>`). A slot is claimed with a single atomic conditional update *before* the
  provider is called, so concurrent requests and several workers can never pass 100; the 101st is
  refused. A warning is logged from the 95th. A slot is given back only when the provider
  definitely did not send (HTTP error, connection refused); a timeout keeps it, because the email
  may have gone out. When the allowance is gone every address gets the same `503
  EMAIL_DAILY_LIMIT_REACHED` (checked before the account lookup), and losing the race for the very
  last slot looks like an unknown account, so account existence is never revealed. Per-address
  (5/day) and per-network (20/day) caps stop one person from using up everybody's allowance.
- **Storage ceiling (R2, 9.7 GB).** One counter (`r2_bytes`) is reserved atomically before any
  write (original + preview + thumbnail, or a quote preview) and released for exactly the bytes
  that are really gone after a failure, delete or cleanup. Concurrent uploads near the ceiling
  cannot exceed it. A maintenance job (every 6 h, one worker at a time through a MongoDB lease)
  retries failed deletions, deletes quote previews more than 31 days old that no live quote
  references (never anything outside `quotes/`), and re-measures the bucket to correct drift with a
  compare-and-set, so a concurrent upload is never overwritten.
- **Upload size and decode memory.** 2 MB per photo and per quote preview (413 while streaming),
  plus a 25-megapixel cap read from the image header before pixels are decoded (decompression
  bombs). The browser shrinks bigger photos first, up to 40 MB of input.
- **Accounts.** At most 20 new accounts per network per day (password and Google sign-up); only
  successful sign-ups count.
- **Groq (optional, off by default).** Smart layouts need a signed-in user. A request slot is
  claimed atomically before the call: 10 per user and 100 per day for everyone (shared across
  workers), plus a 50,000-token daily budget. Without a key/flag no slot is spent.
- **Diagnostics.** `GET /health` (token-protected outside development) shows counts and sizes only
  (emails used today, stored bytes, database size), never addresses or keys, and caches provider
  probes for 60 s so a monitor cannot become a stream of provider calls.
- **Production start-up refuses** the mock email provider, the Resend `onboarding@resend.dev`
  sender, the placeholder WhatsApp number, `DEBUG`, `LOG_LEVEL=DEBUG`, `SameSite=None`, a localhost
  database, non-https CORS origins or app URL, and a short diagnostics token.
- **Limits of these guarantees.** They are counters kept by this app. They cannot see usage that
  happens outside it (another app on the same Resend account or R2 bucket, objects added in the
  Cloudflare dashboard until the next maintenance run) and they do not replace the providers' own
  billing alerts. Set those too (see backend/README.md, "Free-tier operations").

## Quote requests and reports (Phase 6, 2026-11-12)

- **A quote is the saved design.** The planner saves first (with the customer's confirmation), then
  sends the saved design's id; the server checks the design is the caller's and that every quoted
  wall, layout and frame value equals the saved version. Unsaved edits can never reach a report, and
  someone else's design id is a 403.
- **No duplicates.** The planner holds one request key per design content and reuses it (and the
  rendered preview) for retries; the server enforces one quote per (user, `Idempotency-Key`) with a
  unique index, so double clicks, retries and races create one quote. A replay re-issues the share link.
- **The WhatsApp link is untrusted input.** The client opens only `https://wa.me/…`
  (also `api.whatsapp.com`, `web.whatsapp.com`) without credentials, and the report link only if it is
  the app's own `/q/<token>`; anything else is dropped. "Open WhatsApp" is a normal link with
  `rel="noopener noreferrer"`, clicked by the customer, so it isn't a blocked popup and the new tab
  can't reach the planner. Nothing is sent automatically.
- **Preview image.** Rendered in the browser from what's on screen, sent as multipart, and checked on
  the server from its bytes (PNG/WebP/JPEG signature, decoded, 100–8192 px, ≤ 2 MB); SVG/HTML,
  GIF, truncated, empty, tiny and oversize files are refused before anything is stored.
- **The report** is public only by an unguessable token (256 bits, only a hash is stored) and expires
  (30 days → 404). It shows the customer's name but masks mobile and email, never shows internal
  ids or storage keys, escapes every user string, and ships a CSP with no scripts and no third-party
  requests, `Referrer-Policy: no-referrer` and `Cache-Control: private, no-store`. The photo column
  shows file names (so the studio can match files): don't name photos with private details.
- Preview files of expired quotes are deleted by the storage maintenance job (see Phase 7 below).

## Planner data (Phase 5, 2026-11-12)

- **Photos** are served by signed, expiring URLs (`?sig&exp`, HMAC over id + kind + expiry), so
  `<img>` needs no token in the URL or a header. The signature binds the photo id and the kind
  (a thumbnail signature can't open the preview), and tampering with `exp` invalidates it. Ownership
  is checked on upload, list, delete and when a design references a photo (403 for someone else's).
- **Deleting** a photo that a live design uses is refused (409), so designs never silently lose
  their pictures. A user can't learn who else uses a photo: the ownership check comes first.
- **Uploads** are checked on the client (type, 2 MB after shrinking, pixel size) and again on the server from the
  file's content (magic bytes, decoded and re-encoded, EXIF applied, 300–8192 px). SVG/HTML/PHP
  payloads and truncated or oversized files are rejected; filenames are only labels (storage keys
  use the photo id) and are rendered as text.
- **Design search** is a literal substring match: user text is escaped before it reaches MongoDB's
  `$regex` (it used to be a raw regular expression: invalid patterns errored, crafted ones could
  burn CPU).
- **Unsaved work** is kept in `sessionStorage` (this tab only): design content and photo ids, no
  tokens, no photo bytes, no URLs. It belongs to one user id, is rebuilt through the same sanitiser as
  any untrusted data, and is deleted on deliberate sign-out.
- **Catalog and API data** are validated before use: a malformed `/catalog` is ignored as a whole,
  invalid templates are skipped, and a design read back from the API goes through
  `sanitizePlannerState` (unknown ids → defaults, numbers clamped, unsafe photo/sample ids dropped).
- **PNG export** requests cross-origin photos in CORS mode (the API echoes the allowed frontend
  origin), so the canvas isn't tainted; production needs the frontend origin in `CORS_ORIGINS`.

## Frontend session handling (Phase 4, 2026-11-12)

- **Restore:** `AuthProvider` calls `POST /auth/refresh` (cookie sent automatically) and then
  `GET /auth/me` once per page load. Routes wait on that (`PageLoader`), so a reload never flashes
  the sign-in page. A `401` means signed out; a network failure also lands on sign-in, with an
  honest "couldn't reach the server" notice instead of "expired".
- **Renewal:** `apiClient` refreshes on a `401` (or before sending with a known-expired token) and
  replays the request once. Concurrent callers share **one** `/auth/refresh` (single-flight), and a
  caller whose token was already renewed by someone else just replays. A rejected refresh ends the
  session; a network failure does not.
- **Guards:** `ProtectedRoute` (planner) and `GuestRoute` (login, register, forgot password).
  The post-login target comes only from router state and is accepted only as a same-app absolute
  path that isn't an auth page (`lib/redirect.ts`), so it can't become an open redirect.
- **Sign out:** `POST /auth/logout` revokes the session and clears the cookie. If the server can't be
  reached the user stays signed in and is told, because JavaScript can't clear an httpOnly cookie and
  a reload would otherwise restore the session.
- **Storage:** nothing auth-related is written to `localStorage`, `sessionStorage`, the URL or logs.
  The reset email, OTP and reset token live in component state only. Google's ID token is forwarded
  to `POST /auth/google` and dropped.
- **Account enumeration:** the forgot-password screens say "if an account exists" for every email;
  sign-in failures (401/403) ignore field details and show one generic message.

Backend fix found while testing this phase: a refresh cookie rotated less than 30 s earlier (the
"concurrent tab" grace) could still mint an access token **after logout or a password reset**. The
grace now applies only while the session family is still active.
