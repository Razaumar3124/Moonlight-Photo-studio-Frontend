import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import argon2
import jwt

from app.core.config import get_settings

# Argon2id password hasher configuration (NIST & OWASP recommended profile)
_hasher = argon2.PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    type=argon2.Type.ID,
)

# Indian mobile regex (starts with 6-9, followed by 9 digits)
_INDIAN_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")
_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash in constant time."""
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.VerificationError):
        return False
    except Exception:
        return False


def hash_token(raw_token: str) -> str:
    """Compute SHA-256 hash of a raw token for secure database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a high-entropy URL-safe cryptographic token string."""
    return secrets.token_urlsafe(nbytes)


def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit numeric OTP (100000-999999)."""
    return f"{secrets.randbelow(900000) + 100000}"


def generate_reset_token() -> str:
    """Generate a high-entropy, prefixed single-use password reset session token."""
    return f"rst_{secrets.token_urlsafe(32)}"


def hash_otp(email: str, otp: str) -> str:
    """Compute HMAC-SHA256 hash of a numeric OTP bound to the recipient's email.

    Using HMAC with a server-side secret prevents brute-force rainbow table lookups
    on short 6-digit numeric codes even if the database is exposed.
    """
    settings = get_settings()
    secret = (settings.OTP_SECRET_KEY.strip() or settings.SECRET_KEY).encode("utf-8")
    message = f"{email.strip().lower()}:{otp}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_otp_hash(email: str, candidate_otp: str, stored_hash: str) -> bool:
    """Verify candidate OTP against stored HMAC-SHA256 in constant time."""
    candidate_hash = hash_otp(email, candidate_otp)
    return constant_time_compare(candidate_hash, stored_hash)


def constant_time_compare(val1: str, val2: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return hmac.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))


def create_access_token(
    subject: str,
    role: str = "customer",
    expires_delta: timedelta | None = None,
) -> tuple[str, int]:
    """Generate a signed JWT access token.

    Returns:
        tuple[str, int]: (encoded_jwt_token, expires_in_seconds)
    """
    settings = get_settings()
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_in_seconds = int(delta.total_seconds())

    now = datetime.now(UTC)
    expire_time = now + delta

    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire_time.timestamp()),
        "jti": secrets.token_hex(16),
    }

    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, expires_in_seconds


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and cryptographically verify a JWT access token.

    Raises:
        jwt.PyJWTError: If token is expired, forged, or malformed.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub"]},
    )


def normalize_email(email: str) -> str:
    """Normalize email address to lowercase and trimmed."""
    return email.strip().lower()


def normalize_phone(raw: str, default_country_code: str = "+91") -> str | None:
    """Normalize phone input to E.164 international format.

    Handles formats like:
    - 9876543210 -> +919876543210
    - 09876543210 -> +919876543210
    - 919876543210 -> +919876543210
    - +919876543210 -> +919876543210
    """
    compact = re.sub(r"[\s\-().]", "", raw.strip())
    if not compact:
        return None

    if compact.startswith("+"):
        return compact if _E164_RE.match(compact) else None

    # Remove leading trunk zero: 09876543210 -> 9876543210
    digits = re.sub(r"^0+", "", compact)

    if _INDIAN_MOBILE_RE.match(digits):
        return f"{default_country_code}{digits}"

    # Handle typed country code without plus: 919876543210
    if digits.startswith("91") and len(digits) == 12 and _INDIAN_MOBILE_RE.match(digits[2:]):
        return f"+{digits}"

    return None


def get_client_ip(request: Any) -> str | None:
    """Extract client IP, inspecting trusted proxy headers if present.

    Checks headers in order of specificity:
    1. CF-Connecting-IP (Cloudflare)
    2. X-Forwarded-For (client IP is first in comma-separated list)
    3. X-Real-IP (standard reverse proxy)
    4. Direct socket client host (request.client.host)
    """
    if not request:
        return None

    headers = getattr(request, "headers", None)
    if headers:
        cf_ip = headers.get("cf-connecting-ip")
        if cf_ip and cf_ip.strip():
            return cf_ip.strip()

        x_forwarded = headers.get("x-forwarded-for")
        if x_forwarded and x_forwarded.strip():
            client_candidate = x_forwarded.split(",")[0].strip()
            if client_candidate:
                return client_candidate

        real_ip = headers.get("x-real-ip")
        if real_ip and real_ip.strip():
            return real_ip.strip()

    client = getattr(request, "client", None)
    return client.host if client else None


def generate_photo_signature(photo_id: str, kind: str, expires_at: int) -> str:
    """Generate an HMAC-SHA256 signature for secure short-lived media access."""
    settings = get_settings()
    message = f"{photo_id}:{kind}:{expires_at}"
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:24]


def verify_photo_signature(photo_id: str, kind: str, sig: str, expires_at: int) -> bool:
    """Validate an HMAC-SHA256 photo media signature in constant time."""
    now_ts = int(datetime.now(UTC).timestamp())
    if expires_at < now_ts:
        return False
    expected = generate_photo_signature(photo_id, kind, expires_at)
    return constant_time_compare(sig, expected)
