"""Fixed free-tier safeguards.

These are product/safety limits, not deployment settings, so they live in code instead of
``.env`` (nobody can raise one by accident). Code reads them through the module
(``limits.EMAIL_DAILY_LIMIT``) at call time, so tests can patch a single value.
"""

# --- Resend (free tier: 100 emails per UTC day) -------------------------------------------
EMAIL_DAILY_LIMIT = 100  # the 101st email of a UTC day is refused
EMAIL_WARN_AT = 95  # a warning is logged (and shown in diagnostics) from this count

# Per-address / per-network daily caps on password-reset requests, so one person cannot use up
# the shared allowance above.
FORGOT_PASSWORD_EMAIL_DAILY = 5
FORGOT_PASSWORD_IP_DAILY = 20

# --- Cloudflare R2 (free tier: 10 GB-month; 1 GB = 10^9 bytes) ----------------------------
# Hard ceiling for everything stored: originals, previews, thumbnails and quote previews.
R2_STORAGE_LIMIT_BYTES = 9_700_000_000
R2_STORAGE_WARN_FRACTION = 0.9

# --- Photo uploads -------------------------------------------------------------------------
PHOTO_MAX_BYTES = 2 * 1024 * 1024  # 2 MB per photo (the browser shrinks larger ones first)
PHOTO_MAX_PIXELS = 25_000_000  # width x height; guards decode memory (decompression bombs)

# --- Quote preview images ------------------------------------------------------------------
QUOTE_PREVIEW_MAX_BYTES = 2 * 1024 * 1024
QUOTE_SHARE_EXPIRY_DAYS = 30
# Stored previews are removed this many days after their quote expired (report is 404 by then).
QUOTE_PREVIEW_GRACE_DAYS = 1

# --- Registration --------------------------------------------------------------------------
REGISTER_DAILY_PER_IP = 20  # accounts created from one IP per day (shared networks fit)

# --- Groq (optional AI layout curator; free tier has request/token limits) -------------------
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TIMEOUT_SECONDS = 10
GROQ_MAX_OUTPUT_TOKENS = 256
GROQ_DAILY_REQUEST_LIMIT = 100  # shared across all users and workers
GROQ_DAILY_REQUESTS_PER_USER = 10
GROQ_DAILY_TOKEN_BUDGET = 50_000  # shared across all users and workers

# --- Health diagnostics --------------------------------------------------------------------
HEALTH_PROVIDER_CACHE_SECONDS = 60  # external provider probes are reused for this long
USAGE_DIAGNOSTICS_CACHE_SECONDS = 300  # MongoDB size stats are reused for this long

# --- Background storage maintenance ---------------------------------------------------------
MAINTENANCE_INTERVAL_SECONDS = 6 * 3600
