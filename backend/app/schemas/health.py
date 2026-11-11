from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthLiveResponse(BaseModel):
    """Response schema for GET /api/v1/health/live."""

    status: str = Field(default="ok", description="Liveness status indicator", examples=["ok"])
    service: str = Field(
        default="saf-studio-api",
        description="Service identifier",
        examples=["saf-studio-api"],
    )
    version: str = Field(default="0.1.0", description="API application version", examples=["0.1.0"])
    uptime_seconds: float = Field(
        ...,
        description="Application uptime in seconds",
        examples=[124.5],
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "status": "ok",
                "service": "saf-studio-api",
                "version": "0.1.0",
                "uptime_seconds": 3600.0,
            }
        },
    )


class DatabaseHealthStatus(BaseModel):
    """Detailed health status for the MongoDB database connection."""

    connected: bool = Field(default=True, description="Whether MongoDB is reachable")
    status: str = Field(default="connected", description="Connection status message")
    latency_ms: float | None = Field(
        default=None,
        description="Round-trip ping latency in milliseconds",
        examples=[1.2],
    )

    model_config = ConfigDict(extra="forbid")


class StorageHealthStatus(BaseModel):
    """Detailed health status for Cloudflare R2 object storage."""

    connected: bool = Field(default=True, description="Whether Cloudflare R2 bucket is reachable")
    status: str = Field(default="connected", description="R2 storage status description")
    bucket: str = Field(..., description="Target Cloudflare R2 bucket name")
    latency_ms: float | None = Field(default=None, description="Round-trip S3 ping latency in ms")
    issue: str | None = Field(default=None, description="Diagnostic issue message if unavailable")

    model_config = ConfigDict(extra="forbid")


class EmailHealthStatus(BaseModel):
    """Detailed health status for the transactional email provider."""

    status: str = Field(..., description="Email service status: ready, degraded, or misconfigured")
    provider: str = Field(..., description="Active email provider: resend or mock")
    from_email: str | None = Field(default=None, description="Configured sender email address")
    latency_ms: float | None = Field(default=None, description="Resend API latency in milliseconds")
    mock_emails_queued: int | None = Field(
        default=None, description="Number of mocked emails queued in dev"
    )
    issue: str | None = Field(default=None, description="Diagnostic issue message if degraded")

    model_config = ConfigDict(extra="forbid")


class WhatsAppHealthStatus(BaseModel):
    """Detailed health status for WhatsApp quote integration."""

    status: str = Field(
        ..., description="WhatsApp integration status: configured or invalid_configuration"
    )
    business_number: str = Field(..., description="Configured business WhatsApp number")
    is_placeholder: bool = Field(
        default=False, description="Whether the number is an unconfigured placeholder"
    )
    is_valid_format: bool = Field(
        default=True, description="Whether the number is valid E.164"
    )
    public_app_url: str = Field(..., description="Base URL used for shareable quote reports")

    model_config = ConfigDict(extra="forbid")


class GroqHealthStatus(BaseModel):
    """Detailed health status for Groq AI creative curator inference."""

    status: str = Field(
        ..., description="Groq inference status: ready, disabled, degraded, or unreachable"
    )
    enabled: bool = Field(default=False, description="Whether Groq AI inference is active")
    model: str = Field(..., description="Configured LLM model identifier")
    latency_ms: float | None = Field(
        default=None, description="Round-trip inference latency in ms"
    )
    issue: str | None = Field(
        default=None, description="Diagnostic issue message if degraded"
    )

    model_config = ConfigDict(extra="forbid")


class GoogleAuthHealthStatus(BaseModel):
    """Detailed health status for Google OAuth and token verification."""

    status: str = Field(..., description="Google auth status: ready or degraded")
    client_id_configured: bool = Field(
        default=True, description="Whether a valid Google Client ID is configured"
    )
    certs_reachable: bool = Field(
        default=True, description="Whether Google public certs are reachable"
    )
    latency_ms: float | None = Field(
        default=None, description="Google certs endpoint latency in ms"
    )
    issue: str | None = Field(
        default=None, description="Diagnostic issue if Google certs unreachable"
    )

    model_config = ConfigDict(extra="forbid")


class HealthComponentsStatus(BaseModel):
    """Container for all subsystem diagnostic statuses."""

    database: DatabaseHealthStatus
    storage: StorageHealthStatus | None = None
    email: EmailHealthStatus | None = None
    whatsapp: WhatsAppHealthStatus | None = None
    groq_ai: GroqHealthStatus | None = None
    google_oauth: GoogleAuthHealthStatus | None = None

    model_config = ConfigDict(extra="forbid")


class HealthReadyResponse(BaseModel):
    """Response schema for GET /api/v1/health/ready."""

    status: str = Field(
        default="ready",
        description="Readiness status indicator",
        examples=["ready"],
    )
    service: str = Field(
        default="saf-studio-api",
        description="Service identifier",
        examples=["saf-studio-api"],
    )
    database: DatabaseHealthStatus = Field(
        ...,
        description="Database connectivity details",
    )
    storage: StorageHealthStatus | None = Field(
        default=None,
        description="Cloudflare R2 storage status",
    )
    email: EmailHealthStatus | None = Field(
        default=None,
        description="Email service status",
    )
    whatsapp: WhatsAppHealthStatus | None = Field(
        default=None,
        description="WhatsApp quote integration status",
    )
    groq_ai: GroqHealthStatus | None = Field(
        default=None,
        description="Groq AI curator inference status",
    )
    google_oauth: GoogleAuthHealthStatus | None = Field(
        default=None,
        description="Google OAuth token verification status",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Readiness verification timestamp",
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "status": "ready",
                "service": "saf-studio-api",
                "database": {
                    "connected": True,
                    "status": "connected",
                    "latency_ms": 1.2,
                },
                "timestamp": "2026-11-07T12:00:00.000Z",
            }
        },
    )


class HealthSystemResponse(BaseModel):
    """Comprehensive system-wide health response for GET /api/v1/health."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        default="healthy",
        description="Overall system health status",
        examples=["healthy"],
    )
    service: str = Field(
        default="saf-studio-api",
        description="Service identifier",
        examples=["saf-studio-api"],
    )
    version: str = Field(
        default="0.1.0",
        description="API application version",
        examples=["0.1.0"],
    )
    uptime_seconds: float = Field(
        ...,
        description="Application uptime in seconds",
        examples=[124.5],
    )
    components: HealthComponentsStatus = Field(
        ...,
        description="Health status breakdown per subsystem",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Verification timestamp",
    )

    model_config = ConfigDict(extra="forbid")
