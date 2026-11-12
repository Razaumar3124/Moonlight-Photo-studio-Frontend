import ipaddress
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/ (this file is backend/app/core/config.py). Anchors .env and local storage so the
# server behaves the same whether it is started from backend/ or from the repository root.
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Development-only fallback. Rejected when ENVIRONMENT=production (see
# validate_production_requirements); generate real keys for every other environment too.
INSECURE_DEV_SECRET_KEY = "dev-insecure-secret-key-change-me-moonlight-studio-local-only"

# Placeholder business number shipped as a default; must be replaced in production.
PLACEHOLDER_WHATSAPP_NUMBER = "919876543210"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    # Application metadata
    APP_NAME: str = Field(
        default="Moonlight Photo Studio API",
        description="Human-readable application name",
    )
    VERSION: str = Field(default="0.1.0", description="API version string")
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        description="Application running environment",
    )
    DEBUG: bool = Field(default=False, description="Enable debug mode and verbose documentation")
    HOST: str = Field(default="0.0.0.0", description="Server bind host")
    PORT: int = Field(default=8000, description="Server bind port")
    API_V1_STR: str = Field(default="/api/v1", description="URL prefix for API version 1")

    # MongoDB connection settings
    MONGODB_URL: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URI",
    )
    DATABASE_NAME: str = Field(
        default="moonlight_studio",
        description="MongoDB database name",
    )
    MONGODB_TIMEOUT_MS: int = Field(
        default=10000,
        description="Connection and server selection timeout in milliseconds",
    )

    # CORS settings
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="List of allowed CORS origins",
    )

    # Structured logging level
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Application log level",
    )

    # JWT & Authentication security
    SECRET_KEY: str = Field(
        default=INSECURE_DEV_SECRET_KEY,
        description="Cryptographic secret key for signing JWT tokens (min 32 chars)",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token validity lifetime in minutes",
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=14,
        description="Refresh token validity lifetime in days",
    )
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60,
        description="Password reset token expiration in minutes",
    )

    # Cookie settings for refresh token
    REFRESH_COOKIE_NAME: str = Field(
        default="refresh_token", description="Name of the refresh cookie"
    )
    COOKIE_SECURE: bool = Field(
        default=False,
        description="Whether refresh cookie requires HTTPS. Set to True in production.",
    )
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = Field(
        default="lax",
        description="SameSite cookie policy",
    )
    COOKIE_DOMAIN: str | None = Field(
        default=None, description="Optional cookie domain restriction"
    )
    REFRESH_COOKIE_PATH: str | None = Field(
        default=None,
        description="Path scope of the refresh cookie (default: '<API_V1_STR>/auth')",
    )
    REFRESH_REUSE_GRACE_SECONDS: int = Field(
        default=30,
        ge=0,
        le=300,
        description=(
            "A refresh token rotated less than this many seconds ago is treated as a "
            "concurrent refresh (e.g. two tabs), not as token theft"
        ),
    )

    # Reverse proxies whose X-Forwarded-For / X-Real-IP headers are trusted (see get_client_ip).
    # Empty = trust none: the socket peer address is the client IP.
    TRUSTED_PROXIES: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="IPs or CIDR ranges of trusted reverse proxies (JSON list or comma-separated)",
    )

    # Request body limits, enforced while streaming (before anything is buffered in memory)
    MAX_REQUEST_BODY_BYTES: int = Field(
        default=1024 * 1024,
        ge=16 * 1024,
        description="Maximum body size for non-upload requests",
    )
    QUOTE_PREVIEW_MAX_MB: int = Field(
        default=15, ge=1, le=50, description="Maximum quote preview image size in megabytes"
    )

    # Detailed /health diagnostics: open in development; elsewhere requires this token
    # in the X-Health-Token header (empty = detailed diagnostics disabled outside development).
    HEALTH_DIAGNOSTICS_TOKEN: str = Field(
        default="", description="Token for GET /health detailed diagnostics"
    )

    # Google OAuth client ID
    GOOGLE_CLIENT_ID: str = Field(
        default="",
        description="Google OAuth 2.0 Web Client ID for validating Google ID tokens",
    )

    # Rate limiting. "mongodb" shares counters across workers/instances (TTL collection);
    # "memory" is per-process and bounded (tests, single-process development).
    RATE_LIMIT_BACKEND: Literal["mongodb", "memory"] = Field(
        default="mongodb",
        description="Rate-limit counter store. Production requires 'mongodb'.",
    )
    RATE_LIMIT_LOGIN_MAX_ATTEMPTS: int = Field(
        default=5,
        description="Maximum login attempts within window per client IP + identifier",
    )
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = Field(
        default=300,
        description="Time window in seconds for login rate limiting",
    )
    RATE_LIMIT_LOGIN_IDENTIFIER_MAX_ATTEMPTS: int = Field(
        default=20,
        description="Maximum login attempts per identifier from all IPs (distributed guessing)",
    )
    RATE_LIMIT_LOGIN_IDENTIFIER_WINDOW_SECONDS: int = Field(default=900)
    RATE_LIMIT_LOGIN_IP_MAX_ATTEMPTS: int = Field(
        default=30,
        description="Maximum login attempts per client IP across identifiers (credential spraying)",
    )
    RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS: int = Field(default=300)
    RATE_LIMIT_REGISTER_MAX_ATTEMPTS: int = Field(
        default=5,
        description="Maximum registrations allowed per IP within window",
    )
    RATE_LIMIT_REGISTER_WINDOW_SECONDS: int = Field(
        default=300,
        description="Time window in seconds for registration rate limiting",
    )
    RATE_LIMIT_PHOTO_UPLOAD_MAX_ATTEMPTS: int = Field(
        default=30,
        description="Maximum photo uploads allowed per user/IP per hour",
    )
    RATE_LIMIT_PHOTO_UPLOAD_WINDOW_SECONDS: int = Field(
        default=3600,
        description="Time window in seconds for photo upload rate limiting",
    )

    # Email & Password Recovery (Resend)
    EMAIL_PROVIDER: Literal["resend", "mock"] = Field(
        default="mock",
        description="Transactional email provider: 'resend' for live API, 'mock' for local dev",
    )
    RESEND_API_KEY: str = Field(
        default="",
        description="Resend REST API key (re_...)",
    )
    RESEND_FROM_EMAIL: str = Field(
        default="Moonlight Photo Studio <onboarding@resend.dev>",
        description="Configured sender email address for transactional recovery emails",
    )
    RESEND_TEST_MODE: bool = Field(
        default=True,
        description="Whether Resend testing mode is enabled to restrict recipient delivery",
    )
    RESEND_TEST_RECIPIENT: str = Field(
        default="",
        description=(
            "Only recipient allowed while RESEND_TEST_MODE is enabled "
            "(the Resend account owner's address)"
        ),
    )
    EMAIL_OTP_EXPIRE_MINUTES: int = Field(
        default=10,
        description="Validity lifetime in minutes for 6-digit password reset OTP codes",
    )
    EMAIL_OTP_COOLDOWN_SECONDS: int = Field(
        default=60,
        description="Minimum cooldown in seconds between OTP requests for the same email address",
    )
    OTP_MAX_ATTEMPTS: int = Field(
        default=3,
        description="Maximum failed OTP verification attempts before locking",
    )
    OTP_SECRET_KEY: str = Field(
        default="",
        description="Dedicated secret key for HMAC-SHA256 OTP hashing (falls back to SECRET_KEY)",
    )
    RATE_LIMIT_FORGOT_PASSWORD_MAX_ATTEMPTS: int = Field(
        default=3,
        description="Maximum OTP requests per email within rate limit window",
    )
    RATE_LIMIT_FORGOT_PASSWORD_WINDOW_SECONDS: int = Field(
        default=900,
        description="Time window in seconds (15 minutes) for per-email OTP rate limiting",
    )
    RATE_LIMIT_FORGOT_PASSWORD_IP_MAX_ATTEMPTS: int = Field(
        default=10,
        description="Maximum OTP requests per IP within rate limit window",
    )
    RATE_LIMIT_FORGOT_PASSWORD_IP_WINDOW_SECONDS: int = Field(
        default=3600,
        description="Time window in seconds (1 hour) for per-IP OTP rate limiting",
    )
    RATE_LIMIT_OTP_VERIFY_IP_MAX_ATTEMPTS: int = Field(default=15)
    RATE_LIMIT_OTP_VERIFY_IP_WINDOW_SECONDS: int = Field(default=300)
    RATE_LIMIT_OTP_VERIFY_EMAIL_MAX_ATTEMPTS: int = Field(
        default=10, description="OTP verification attempts per email across all codes and IPs"
    )
    RATE_LIMIT_OTP_VERIFY_EMAIL_WINDOW_SECONDS: int = Field(default=900)
    RATE_LIMIT_PASSWORD_RESET_IP_MAX_ATTEMPTS: int = Field(default=10)
    RATE_LIMIT_PASSWORD_RESET_IP_WINDOW_SECONDS: int = Field(default=900)

    # Object storage backend: "local" (development filesystem) or "r2" (Cloudflare R2)
    STORAGE_BACKEND: Literal["local", "r2"] = Field(
        default="local",
        description="Object storage for photos and quote previews. Production requires 'r2'.",
    )
    LOCAL_STORAGE_PATH: str = Field(
        default="storage/local",
        description="Root folder for STORAGE_BACKEND=local (relative paths resolve from backend/)",
    )
    LOCAL_STORAGE_URL_EXPIRATION_SECONDS: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Lifetime of signed local-storage download URLs",
    )

    # Cloudflare R2 Object Storage
    R2_ACCOUNT_ID: str = Field(
        default="",
        description="Cloudflare Account ID for R2 storage",
    )
    R2_ACCESS_KEY_ID: str = Field(
        default="",
        description="Cloudflare R2 Access Key ID",
    )
    R2_SECRET_ACCESS_KEY: str = Field(
        default="",
        description="Cloudflare R2 Secret Access Key",
    )
    R2_BUCKET_NAME: str = Field(
        default="moonlight-studio-photos",
        description="Private Cloudflare R2 bucket name for customer photographs",
    )
    R2_CUSTOM_DOMAIN: str = Field(
        default="",
        description="Optional public custom domain for public assets",
    )
    R2_ENDPOINT_URL: str = Field(
        default="",
        description="Explicit S3 endpoint URL override (defaults to Cloudflare R2 standard)",
    )
    R2_MAX_UPLOAD_MB: int = Field(
        default=25,
        description="Maximum allowed photo upload size in megabytes",
    )
    PHOTO_MAX_WIDTH_PX: int = Field(
        default=8192,
        description="Maximum allowed image width in pixels",
    )
    PHOTO_MAX_HEIGHT_PX: int = Field(
        default=8192,
        description="Maximum allowed image height in pixels",
    )
    PHOTO_MIN_SIDE_PX: int = Field(
        default=300,
        description="Minimum allowed image side dimension in pixels for quality printing",
    )
    PHOTO_SIGNED_URL_EXPIRATION_SECONDS: int = Field(
        default=86400,
        description="Validity lifetime in seconds for photo thumbnail and preview HMAC signatures",
    )

    # Business Contact & WhatsApp Quotes (Phase 7)
    BUSINESS_WHATSAPP_NUMBER: str = Field(
        default=PLACEHOLDER_WHATSAPP_NUMBER,
        description="Static business WhatsApp number without +, spaces or special chars",
    )
    PUBLIC_APP_URL: str = Field(
        default="http://localhost:5173",
        description="Public canonical base URL for shareable quote reports and application links",
    )
    QUOTE_SHARE_EXPIRY_DAYS: int = Field(
        default=30,
        description="Validity lifetime in days for shared digital quote design reports",
    )
    RATE_LIMIT_QUOTE_PREPARE_MAX_ATTEMPTS: int = Field(
        default=10,
        description="Maximum quote preparations allowed per user/IP per hour",
    )
    RATE_LIMIT_QUOTE_PREPARE_WINDOW_SECONDS: int = Field(
        default=3600,
        description="Time window in seconds for quote preparation rate limiting",
    )

    # Groq AI Creative Curator
    GROQ_API_KEY: str = Field(default="", description="API Key for Groq cloud inference")
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model ID for layout curation recommendations",
    )
    GROQ_ENABLED: bool = Field(
        default=False,
        description="Whether Groq AI recommendations are enabled",
    )
    GROQ_TIMEOUT_SECONDS: int = Field(
        default=10,
        description="Network timeout in seconds for Groq API calls",
    )
    GROQ_MAX_OUTPUT_TOKENS: int = Field(
        default=256,
        description="Maximum tokens for Groq layout recommendation completion",
    )
    GROQ_DAILY_REQUEST_LIMIT: int = Field(
        default=100,
        description="Maximum daily AI layout requests per user/IP budget",
    )
    GROQ_DAILY_TOKEN_BUDGET: int = Field(
        default=50000,
        description="Maximum daily token consumption allowance across application",
    )

    @field_validator("MONGODB_URL")
    @classmethod
    def validate_mongodb_url(cls, v: str) -> str:
        url = v.strip()
        if not (url.startswith("mongodb://") or url.startswith("mongodb+srv://")):
            raise ValueError(
                "MONGODB_URL must begin with either 'mongodb://' (local/standard) "
                "or 'mongodb+srv://' (MongoDB Atlas SRV connection string)"
            )
        for placeholder in ("<password>", "<db_password>", "<username>"):
            if placeholder in url:
                raise ValueError(
                    f"MONGODB_URL contains unresolved placeholder '{placeholder}'. "
                    "Please replace it with your actual MongoDB Atlas database credentials."
                )
        return url

    @field_validator("BUSINESS_WHATSAPP_NUMBER")
    @classmethod
    def validate_whatsapp_number(cls, v: str) -> str:
        cleaned = v.strip().lstrip("+").replace(" ", "").replace("-", "")
        if not cleaned.isdigit() or not (10 <= len(cleaned) <= 15):
            raise ValueError(
                "BUSINESS_WHATSAPP_NUMBER must be in international format (10-15 digits) "
                "without +, spaces, or special characters"
            )
        return cleaned

    @field_validator("PUBLIC_APP_URL")
    @classmethod
    def validate_public_app_url(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("TRUSTED_PROXIES", mode="before")
    @classmethod
    def assemble_trusted_proxies(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            if v.strip().startswith("["):
                v = json.loads(v)
            else:
                v = [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("TRUSTED_PROXIES")
    @classmethod
    def validate_trusted_proxies(cls, v: list[str]) -> list[str]:
        for entry in v:
            try:
                ipaddress.ip_network(entry, strict=False)
            except ValueError as exc:
                raise ValueError(f"TRUSTED_PROXIES entry is not an IP or CIDR: {entry!r}") from exc
        return v

    @field_validator("REFRESH_COOKIE_PATH")
    @classmethod
    def validate_refresh_cookie_path(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            return None  # empty value in .env = use the default path
        if v is not None and not v.startswith("/"):
            raise ValueError("REFRESH_COOKIE_PATH must start with '/'")
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            text = v.strip()
            if text.startswith("["):
                return json.loads(text)
            return [i.strip() for i in text.split(",") if i.strip()]
        if isinstance(v, list):
            return v
        raise ValueError("CORS_ORIGINS must be a list or comma-separated string")

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_production_cors(cls, v: list[str], info) -> list[str]:
        # Disallow wildcard CORS in production
        env = info.data.get("ENVIRONMENT", "development")
        if env == "production" and ("*" in v or not v):
            raise ValueError("Wildcard or empty CORS_ORIGINS is forbidden in production")
        return v

    @model_validator(mode="after")
    def validate_email_provider_config(self) -> "Settings":
        if self.EMAIL_PROVIDER == "resend" and not self.RESEND_API_KEY.strip():
            raise ValueError(
                "RESEND_API_KEY must be provided when EMAIL_PROVIDER is set to 'resend'"
            )
        return self

    @model_validator(mode="after")
    def validate_production_requirements(self) -> "Settings":
        """Refuse to start production with development defaults or missing integrations.

        Only variable names are reported, never their values.
        """
        if not self.is_production:
            return self

        problems: list[str] = []
        secret = self.SECRET_KEY.strip()
        if secret == INSECURE_DEV_SECRET_KEY or len(secret) < 32:
            problems.append("SECRET_KEY must be a unique random value of at least 32 characters")
        otp_secret = self.OTP_SECRET_KEY.strip()
        if len(otp_secret) < 32 or otp_secret == secret:
            problems.append(
                "OTP_SECRET_KEY must be at least 32 characters and differ from SECRET_KEY"
            )
        if self.DEBUG:
            problems.append("DEBUG must be false")
        if self.RATE_LIMIT_BACKEND != "mongodb":
            problems.append("RATE_LIMIT_BACKEND must be 'mongodb' (shared across workers)")
        if self.STORAGE_BACKEND != "r2":
            problems.append("STORAGE_BACKEND must be 'r2'")
        else:
            missing = [
                name
                for name in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME")
                if not str(getattr(self, name)).strip()
            ]
            if not (self.R2_ACCOUNT_ID.strip() or self.R2_ENDPOINT_URL.strip()):
                missing.insert(0, "R2_ACCOUNT_ID (or R2_ENDPOINT_URL)")
            if missing:
                problems.append("missing " + ", ".join(missing))
        if self.EMAIL_PROVIDER != "resend":
            problems.append("EMAIL_PROVIDER must be 'resend' (mock drops password-reset codes)")
        elif self.RESEND_TEST_MODE:
            problems.append("RESEND_TEST_MODE must be false")
        if self.GROQ_ENABLED and not self.GROQ_API_KEY.strip():
            problems.append("GROQ_API_KEY is required when GROQ_ENABLED is true")
        if self.BUSINESS_WHATSAPP_NUMBER == PLACEHOLDER_WHATSAPP_NUMBER:
            problems.append("BUSINESS_WHATSAPP_NUMBER is still the placeholder")
        if not self.PUBLIC_APP_URL.startswith("https://"):
            problems.append("PUBLIC_APP_URL must use https://")

        if problems:
            raise ValueError("Invalid production configuration: " + "; ".join(problems) + ".")
        return self

    @property
    def local_storage_root(self) -> Path:
        """Absolute root folder for the local storage backend."""
        root = Path(self.LOCAL_STORAGE_PATH).expanduser()
        return root if root.is_absolute() else (BACKEND_DIR / root).resolve()

    @property
    def uses_insecure_dev_secret(self) -> bool:
        return self.SECRET_KEY.strip() == INSECURE_DEV_SECRET_KEY

    @property
    def r2_effective_endpoint_url(self) -> str:
        """Construct the S3-compatible endpoint URL for Cloudflare R2."""
        if self.R2_ENDPOINT_URL:
            return self.R2_ENDPOINT_URL
        if self.R2_ACCOUNT_ID:
            return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        return "https://mock-account.r2.cloudflarestorage.com"

    @property
    def max_upload_bytes(self) -> int:
        """Maximum allowed upload size in bytes."""
        return self.R2_MAX_UPLOAD_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT in ("development", "test")

    @property
    def refresh_cookie_path(self) -> str:
        return self.REFRESH_COOKIE_PATH or f"{self.API_V1_STR.rstrip('/')}/auth"

    @property
    def trusted_proxy_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        return [ipaddress.ip_network(entry, strict=False) for entry in self.TRUSTED_PROXIES]

    @property
    def effective_cookie_secure(self) -> bool:
        """Enforce Secure cookies in production regardless of override."""
        return True if self.is_production else self.COOKIE_SECURE

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        # Validation errors must never echo configuration values (they include secrets).
        hide_input_in_errors=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()
