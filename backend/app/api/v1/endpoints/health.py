import asyncio
import hmac
import time
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import GroqClientDep, SettingsDep, StorageDep
from app.core.config import Settings, get_settings
from app.core.exceptions import ResourceNotFoundException
from app.core.logging import sanitize_sensitive_data
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
from app.storage import ObjectStorage

router = APIRouter(prefix="/health", tags=["Health & Operations"])

HEALTH_TOKEN_HEADER = "X-Health-Token"


def _issue(exc: object) -> str:
    """Diagnostic text for the guarded /health endpoint: credentials masked, length capped."""
    return sanitize_sensitive_data(str(exc))[:200] or type(exc).__name__


async def require_health_diagnostics(request: Request, settings=Depends(get_settings)) -> None:
    """Detailed diagnostics reveal configuration and dependency state.

    Open in development and test; elsewhere only with a matching X-Health-Token header.
    Otherwise the endpoint answers 404, as if it didn't exist.
    """
    if settings.ENVIRONMENT in ("development", "test"):
        return
    expected = settings.HEALTH_DIAGNOSTICS_TOKEN.strip()
    supplied = request.headers.get(HEALTH_TOKEN_HEADER, "")
    if expected and len(expected) >= 16 and hmac.compare_digest(supplied, expected):
        return
    raise ResourceNotFoundException(message="Not found", field="path")


# Module-level start time for uptime calculation
_APP_START_TIME = time.time()


async def _check_r2_storage(storage: ObjectStorage, settings: Settings) -> StorageHealthStatus:
    """Diagnostic check for the configured object storage (local or Cloudflare R2)."""
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
            bucket=storage.bucket_name,
            issue=_issue(exc),
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
            issue=_issue(exc),
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
            issue=_issue(exc),
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
            issue=_issue(exc),
        )


@router.get(
    "",
    response_model=HealthSystemResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_health_diagnostics)],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthSystemResponse,
            "description": "Critical dependency (MongoDB) is unavailable",
        }
    },
    summary="Comprehensive system health check",
    description=(
        "Unified diagnostic probe checking MongoDB, object storage, Email, "
        "WhatsApp, Groq AI, and Google OAuth concurrently."
    ),
)
async def health_system(
    response: Response,
    settings: SettingsDep,
    storage: StorageDep,
    groq_client: GroqClientDep,
) -> HealthSystemResponse:
    """Unified system health check."""

    # 1. Run all health probes concurrently
    async def _safe_db_ping() -> DatabaseHealthStatus:
        try:
            latency = await mongo_manager.ping()
            return DatabaseHealthStatus(connected=True, status="connected", latency_ms=latency)
        except Exception:
            return DatabaseHealthStatus(connected=False, status="disconnected", latency_ms=None)

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
        else DatabaseHealthStatus(connected=False, status="disconnected")
    )
    r2_status = (
        r2_res
        if isinstance(r2_res, StorageHealthStatus)
        else StorageHealthStatus(
            connected=False,
            status="error",
            bucket=storage.bucket_name,
            issue=_issue(r2_res),
        )
    )
    email_status = (
        email_res
        if isinstance(email_res, EmailHealthStatus)
        else EmailHealthStatus(
            status="error",
            provider=settings.EMAIL_PROVIDER,
            issue=_issue(email_res),
        )
    )
    groq_status = (
        groq_res
        if isinstance(groq_res, GroqHealthStatus)
        else GroqHealthStatus(
            status="error",
            enabled=settings.GROQ_ENABLED,
            model=settings.GROQ_MODEL,
            issue=_issue(groq_res),
        )
    )
    google_status = (
        google_res
        if isinstance(google_res, GoogleAuthHealthStatus)
        else GoogleAuthHealthStatus(
            status="error",
            client_id_configured=False,
            certs_reachable=False,
            issue=_issue(google_res),
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
        service="moonlight-studio-api",
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
async def health_live() -> HealthLiveResponse:
    """Liveness probe. Public and minimal; does not depend on any other service."""
    return HealthLiveResponse(status="ok", service="moonlight-studio-api")


@router.get(
    "/ready",
    response_model=HealthReadyResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ApiErrorResponse,
            "description": "Database unreachable",
        }
    },
    summary="Readiness check",
    description=(
        "Public, minimal: confirms the application can reach MongoDB. It makes no calls to "
        "storage, email, AI or Google; use the guarded GET /health for those."
    ),
)
async def health_ready() -> HealthReadyResponse:
    """Readiness probe: MongoDB ping only (503 envelope if unreachable)."""
    latency_ms = await mongo_manager.ping()
    return HealthReadyResponse(
        status="ready",
        service="moonlight-studio-api",
        database=DatabaseHealthStatus(connected=True, status="connected", latency_ms=latency_ms),
    )
