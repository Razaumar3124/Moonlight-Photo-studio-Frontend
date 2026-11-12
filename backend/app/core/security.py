import hashlib
import hmac
import ipaddress
import re
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
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


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    """A genuine Argon2id hash (same parameters as real ones) of a random, discarded secret."""
    return _hasher.hash(secrets.token_urlsafe(32))


def verify_dummy_password(plain_password: str) -> None:
    """Spend the same Argon2id work as a real verification, for accounts that don't exist
    or have no password, so response time doesn't reveal whether an account exists."""
    verify_password(plain_password, _dummy_password_hash())


def warm_up_password_hashing() -> None:
    """Compute the dummy hash at startup so the first unknown-account login isn't faster."""
    _dummy_password_hash()


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
        # Sub-second precision (RFC 7519 NumericDate allows fractions), so a token issued just
        # after a password change is never mistaken for one issued before it.
        "iat": now.timestamp(),
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


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def get_client_ip(request: Any) -> str | None:
    """Client IP for rate limiting and audit logs, resistant to header spoofing.

    Forwarding headers are only honoured when the direct peer is one of TRUSTED_PROXIES.
    ``X-Forwarded-For`` is then read right to left, skipping trusted hops, so values a
    client prepends are ignored. ``X-Real-IP`` is used when no ``X-Forwarded-For`` exists.
    Behind Cloudflare, list Cloudflare's ranges in TRUSTED_PROXIES (its edge appends to
    ``X-Forwarded-For``); ``CF-Connecting-IP`` alone is never trusted.
    """
    if not request:
        return None

    client = getattr(request, "client", None)
    peer = client.host if client else None
    networks = get_settings().trusted_proxy_networks
    peer_ip = _parse_ip(peer) if peer else None
    if not networks or peer_ip is None:
        return peer

    def is_trusted(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return any(ip in network for network in networks)

    if not is_trusted(peer_ip):
        return peer

    headers = getattr(request, "headers", None) or {}
    forwarded = headers.get("x-forwarded-for", "")
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    if not hops and headers.get("x-real-ip"):
        hops = [headers["x-real-ip"].strip()]

    candidate = peer
    for hop in reversed(hops):
        hop_ip = _parse_ip(hop)
        if hop_ip is None:
            break  # malformed entry: don't trust anything further left
        candidate = str(hop_ip)
        if not is_trusted(hop_ip):
            break
    return candidate


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
