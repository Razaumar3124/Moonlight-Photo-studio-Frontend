import asyncio
import time
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Response, status

from app.api.dependencies import GroqClientDep, R2StorageDep, SettingsDep
from app.core.config import Settings
from app.db.mongodb import mongo_manager
from app.integrations.groq_client import GroqClient
from app.schemas.common import ApiErrorResponse
from app.schemas.health import (
    DatabaseHealthStatus,
    EmailHealthStatus,
    GoogleAuthHealthStatus,
    GroqHealthStatus,
    HealthComponentsStatus,
    HealthLiveResponse,
    HealthReadyResponse,
    HealthSystemResponse,
    StorageHealthStatus,
    WhatsAppHealthStatus,
)
from app.services.email_service import email_service
from app.services.whatsapp_service import WhatsAppService
from app.storage.r2_storage import R2Storage

router = APIRouter(prefix="/health", tags=["Health & Operations"])

# Module-level start time for uptime calculation
_APP_START_TIME = time.time()


async def _check_r2_storage(storage: R2Storage, settings: Settings) -> StorageHealthStatus:
    """Diagnostic check for Cloudflare R2 object storage."""
    try:
        latency = await storage.ping()
        return StorageHealthStatus(
            connected=True,
            status="connected",
            bucket=storage.bucket_name,
            latency_ms=latency,
        )
    except Exception as exc:
        return StorageHealthStatus(
            connected=False,
            status="unreachable",
            bucket=settings.R2_BUCKET_NAME,
            issue=str(exc),
        )


async def _check_email_service(settings: Settings) -> EmailHealthStatus:
    """Diagnostic check for transactional email provider."""
    try:
        res = await email_service.check_health()
        return EmailHealthStatus(**res)
    except Exception as exc:
        return EmailHealthStatus(
            status="unreachable",
            provider=settings.EMAIL_PROVIDER,
            from_email=settings.RESEND_FROM_EMAIL,
            issue=str(exc),
        )


def _check_whatsapp_service() -> WhatsAppHealthStatus:
    """Diagnostic check for WhatsApp quote integration."""
    svc = WhatsAppService()
    res = svc.check_health()
    return WhatsAppHealthStatus(**res)


async def _check_groq_client(groq_client: GroqClient, settings: Settings) -> GroqHealthStatus:
    """Diagnostic check for Groq AI creative curator inference."""
    try:
        res = await groq_client.check_health()
        return GroqHealthStatus(**res)
    except Exception as exc:
        return GroqHealthStatus(
            status="unreachable",
            enabled=settings.GROQ_ENABLED,
            model=settings.GROQ_MODEL,
            issue=str(exc),
        )


async def _check_google_oauth(settings: Settings) -> GoogleAuthHealthStatus:
    """Diagnostic check for Google OAuth configuration and certs discovery."""
    client_id = settings.GOOGLE_CLIENT_ID.strip()
    configured = bool(client_id and client_id.endswith(".apps.googleusercontent.com"))

    # In test environment, skip external network call for speed
    if settings.ENVIRONMENT == "test":
        return GoogleAuthHealthStatus(
            status="ready" if configured else "degraded",
            client_id_configured=configured,
            certs_reachable=True,
            latency_ms=1.5,
        )

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("https://www.googleapis.com/oauth2/v3/certs")
        latency = round((time.perf_counter() - start) * 1000, 2)
        certs_ok = resp.status_code == 200
        return GoogleAuthHealthStatus(
            status="ready" if (configured and certs_ok) else "degraded",
            client_id_configured=configured,
            certs_reachable=certs_ok,
            latency_ms=latency,
        )
    except Exception as exc:
        return GoogleAuthHealthStatus(
            status="degraded",
            client_id_configured=configured,
            certs_reachable=False,
            issue=str(exc),
        )


@router.get(
    "",
    response_model=HealthSystemResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthSystemResponse,
            "description": "Critical dependency (MongoDB) is unavailable",
        }
    },
    summary="Comprehensive system health check",
    description=(
        "Unified diagnostic probe checking MongoDB, Cloudflare R2, Email, "
        "WhatsApp, Groq AI, and Google OAuth concurrently."
    ),
)
async def health_system(
    response: Response,
    settings: SettingsDep,
    storage: R2StorageDep,
    groq_client: GroqClientDep,
) -> HealthSystemResponse:
    """Unified system health check."""

    # 1. Run all health probes concurrently
    async def _safe_db_ping() -> DatabaseHealthStatus:
        try:
            latency = await mongo_manager.ping()
            return DatabaseHealthStatus(connected=True, status="connected", latency_ms=latency)
        except Exception as exc:
            return DatabaseHealthStatus(connected=False, status=f"disconnected: {exc}")

    db_res, r2_res, email_res, groq_res, google_res = await asyncio.gather(
        _safe_db_ping(),
        _check_r2_storage(storage, settings),
        _check_email_service(settings),
        _check_groq_client(groq_client, settings),
        _check_google_oauth(settings),
        return_exceptions=True,
    )

    db_status = (
        db_res
        if isinstance(db_res, DatabaseHealthStatus)
        else DatabaseHealthStatus(connected=False, status=str(db_res))
    )
    r2_status = (
        r2_res
        if isinstance(r2_res, StorageHealthStatus)
        else StorageHealthStatus(
            connected=False,
            status="error",
            bucket=settings.R2_BUCKET_NAME,
            issue=str(r2_res),
        )
    )
    email_status = (
        email_res
        if isinstance(email_res, EmailHealthStatus)
        else EmailHealthStatus(
            status="error",
            provider=settings.EMAIL_PROVIDER,
            issue=str(email_res),
        )
    )
    groq_status = (
        groq_res
        if isinstance(groq_res, GroqHealthStatus)
        else GroqHealthStatus(
            status="error",
            enabled=settings.GROQ_ENABLED,
            model=settings.GROQ_MODEL,
            issue=str(groq_res),
        )
    )
    google_status = (
        google_res
        if isinstance(google_res, GoogleAuthHealthStatus)
        else GoogleAuthHealthStatus(
            status="error",
            client_id_configured=False,
            certs_reachable=False,
            issue=str(google_res),
        )
    )
    whatsapp_status = _check_whatsapp_service()

    components = HealthComponentsStatus(
        database=db_status,
        storage=r2_status,
        email=email_status,
        whatsapp=whatsapp_status,
        groq_ai=groq_status,
        google_oauth=google_status,
    )

    # 2. Determine overall health status
    if not db_status.connected:
        overall_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif (
        not r2_status.connected
        or email_status.status in ("degraded", "unreachable", "misconfigured")
        or groq_status.status in ("degraded", "unreachable")
        or google_status.status in ("degraded", "error")
        or whatsapp_status.status == "invalid_configuration"
    ):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    uptime = round(time.time() - _APP_START_TIME, 2)
    return HealthSystemResponse(
        status=overall_status,
        service="saf-studio-api",
        version=settings.VERSION,
        uptime_seconds=uptime,
        components=components,
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get(
    "/live",
    response_model=HealthLiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Confirms that the FastAPI service is running and accepting HTTP requests.",
)
async def health_live(
    settings: SettingsDep,
) -> HealthLiveResponse:
    """Liveness probe. Does not depend on external services."""
    uptime = round(time.time() - _APP_START_TIME, 2)
    return HealthLiveResponse(
        status="ok",
        service="saf-studio-api",
        version=settings.VERSION,
        uptime_seconds=uptime,
    )


@router.get(
    "/ready",
    response_model=HealthReadyResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ApiErrorResponse,
            "description": "Database or external service unreachable",
        }
    },
    summary="Readiness check",
    description="Confirms that the application can reach MongoDB and auxiliary services.",
)
async def health_ready(
    settings: SettingsDep,
    storage: R2StorageDep,
    groq_client: GroqClientDep,
) -> HealthReadyResponse:
    """Readiness probe. Pings MongoDB and auxiliary services."""
    # 1. Critical check: MongoDB must succeed or raise 503
    latency_ms = await mongo_manager.ping()

    # 2. Concurrently probe auxiliary subsystems without blocking readiness
    r2_res, email_res, groq_res, google_res = await asyncio.gather(
        _check_r2_storage(storage, settings),
        _check_email_service(settings),
        _check_groq_client(groq_client, settings),
        _check_google_oauth(settings),
        return_exceptions=True,
    )

    r2_status = r2_res if isinstance(r2_res, StorageHealthStatus) else None
    email_status = email_res if isinstance(email_res, EmailHealthStatus) else None
    groq_status = groq_res if isinstance(groq_res, GroqHealthStatus) else None
    google_status = google_res if isinstance(google_res, GoogleAuthHealthStatus) else None
    whatsapp_status = _check_whatsapp_service()

    return HealthReadyResponse(
        status="ready",
        service="saf-studio-api",
        database=DatabaseHealthStatus(
            connected=True,
            status="connected",
            latency_ms=latency_ms,
        ),
        storage=r2_status,
        email=email_status,
        whatsapp=whatsapp_status,
        groq_ai=groq_status,
        google_oauth=google_status,
    )
