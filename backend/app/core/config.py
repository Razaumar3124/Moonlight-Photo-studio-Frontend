from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    # Application metadata
    APP_NAME: str = Field(default="SAF Studio API", description="Human-readable application name")
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
        default="saf_studio",
        description="MongoDB database name",
    )
    MONGODB_TIMEOUT_MS: int = Field(
        default=10000,
        description="Connection and server selection timeout in milliseconds",
    )

    # CORS settings
    CORS_ORIGINS: list[str] = Field(
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
        default="dev-insecure-secret-key-change-in-production-min-32-chars-saf-studio-2026",
        description="Cryptographic secret key for signing JWT tokens",
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

    # Google OAuth client ID
    GOOGLE_CLIENT_ID: str = Field(
        default="",
        description="Google OAuth 2.0 Web Client ID for validating Google ID tokens",
    )

    # Rate limiting thresholds (in-memory token bucket / sliding window)
    RATE_LIMIT_LOGIN_MAX_ATTEMPTS: int = Field(
        default=5,
        description="Maximum failed login attempts within window per identifier/IP",
    )
    RATE_LIMIT_LOGIN_WINDOW_SECONDS: int = Field(
        default=300,
        description="Time window in seconds for login rate limiting",
    )
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
        default="SAF Studio <onboarding@resend.dev>",
        description="Configured sender email address for transactional recovery emails",
    )
    RESEND_TEST_MODE: bool = Field(
        default=True,
        description="Whether Resend testing mode is enabled to restrict recipient delivery",
    )
    RESEND_TEST_RECIPIENT: str = Field(
        default="abdurrazzakshaikh31@gmail.com",
        description="Permitted testing recipient email during development when RESEND_TEST_MODE is enabled",
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
        default="saf-studio-photos",
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
        default="919876543210",
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

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        if isinstance(v, (list, str)):
            return v  # type: ignore[return-value]
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
    def effective_cookie_secure(self) -> bool:
        """Enforce Secure cookies in production regardless of override."""
        return True if self.is_production else self.COOKIE_SECURE

    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()
