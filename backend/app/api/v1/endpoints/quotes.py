"""FastAPI endpoints for WhatsApp quote requests and digital design reports (Phase 7)."""

import json
import logging
from typing import Any

from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse

from app.api.dependencies import (
    CurrentUserDep,
    QuoteReportServiceDep,
    QuoteServiceDep,
    SettingsDep,
)
from app.core.exceptions import ValidationException
from app.schemas.common import ApiErrorResponse
from app.schemas.quote import (
    QuoteDetailResponse,
    QuotePrepareInput,
    QuotePrepareResponse,
    QuoteShareResponse,
)
from app.services.rate_limiter import rate_limiter

logger = logging.getLogger("saf_studio.quotes")

router = APIRouter(prefix="/quotes", tags=["Quotes"])


@router.post(
    "/prepare",
    response_model=QuotePrepareResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ApiErrorResponse,
            "description": "Invalid design payload or corrupt preview image",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Authentication required to request a quote",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ApiErrorResponse,
            "description": "Photo ownership validation failed",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ApiErrorResponse,
            "description": "Validation failure on wall dimensions or frames",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ApiErrorResponse,
            "description": "Quote preparation rate limit exceeded",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ApiErrorResponse,
            "description": "Storage or database temporarily unavailable",
        },
    },
    summary="Capture design and prepare WhatsApp quote request",
    description=(
        "Captures the customer's current memory wall configuration, validates frames, "
        "uploads high-resolution preview to Cloudflare R2, creates an immutable quote snapshot, "
        "and generates a Click-to-Chat WhatsApp URL for the customer to review and send."
    ),
)
async def prepare_quote(
    request: Request,
    current_user: CurrentUserDep,
    quote_service: QuoteServiceDep,
    settings: SettingsDep,
    file: UploadFile = File(description="Rendered wall preview image (PNG, WebP, or JPEG)"),
    design_data: str = Form(description="JSON string containing current wall planner state"),
) -> QuotePrepareResponse:
    """Prepare a quote request via WhatsApp Click-to-Chat."""
    # 1. Enforce rate limiting
    rate_limiter.check_rate_limit(
        key=f"quote_prepare:{current_user.id}",
        max_attempts=settings.RATE_LIMIT_QUOTE_PREPARE_MAX_ATTEMPTS,
        window_seconds=settings.RATE_LIMIT_QUOTE_PREPARE_WINDOW_SECONDS,
    )

    # 2. Parse design payload JSON
    try:
        raw_json = json.loads(design_data)
        design_input = QuotePrepareInput.model_validate(raw_json)
    except json.JSONDecodeError as exc:
        raise ValidationException(
            message="Invalid design_data format. Expected valid JSON string.",
            details=[{"field": "design_data", "issue": f"JSON decode error: {exc}"}],
        ) from exc
    except Exception as exc:
        raise ValidationException(
            message="Design configuration fails validation constraints.",
            details=[{"field": "design_data", "issue": str(exc)}],
        ) from exc

    # 3. Read image bytes
    preview_bytes = await file.read()

    # 4. Process quote through quote service
    response = await quote_service.prepare_quote(
        current_user=current_user,
        design_input=design_input,
        preview_bytes=preview_bytes,
    )
    return response


@router.get(
    "/share/{token}",
    response_model=QuoteShareResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ApiErrorResponse,
            "description": "Shared quote report not found or link has expired",
        },
    },
    summary="Retrieve secure read-only design report",
    description=(
        "Retrieves the public, read-only digital design report for an active quote share token. "
        "Returns responsive HTML by default or JSON if requested via Accept: application/json."
    ),
)
async def get_shared_quote(
    token: str,
    quote_service: QuoteServiceDep,
    report_service: QuoteReportServiceDep,
    accept: str | None = Header(default=None),
) -> Any:
    """Retrieve the digital design report by its secure share token."""
    quote, preview_url = await quote_service.get_quote_by_share_token(token)

    # If client explicitly asks for JSON, return structured schema
    if accept and "application/json" in accept and "text/html" not in accept:
        return report_service.build_share_response(quote, preview_url)

    # By default, render full responsive branded HTML report
    html_content = report_service.render_report_html(quote, preview_url)
    return HTMLResponse(content=html_content)


@router.get(
    "/share/{token}/preview",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ApiErrorResponse,
            "description": "Preview media not found or share token expired",
        },
    },
    summary="Stream preview image for shared digital report",
    description=(
        "Securely streams the quote's wall preview image from Cloudflare R2 "
        "for verified share token holders."
    ),
)
async def get_shared_quote_preview(
    token: str,
    quote_service: QuoteServiceDep,
) -> Response:
    """Stream high-res preview image for an authorized share token holder without authentication."""
    quote, _ = await quote_service.get_quote_by_share_token(token)
    data, content_type = await quote_service.r2_storage.get_object(quote.preview_image_key)

    return Response(
        content=data,
        media_type=content_type or quote.preview_image_content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": f'inline; filename="saf-quote-{quote.quote_reference}.png"',
        },
    )


@router.get(
    "/{id}",
    response_model=QuoteDetailResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Authentication required to retrieve quote",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ApiErrorResponse,
            "description": "Quote not found or not owned by user",
        },
    },
    summary="Retrieve an authorized quote record",
    description="Returns authorized quote specifications and details for the authenticated owner.",
)
async def get_quote_by_id(
    id: str,
    current_user: CurrentUserDep,
    quote_service: QuoteServiceDep,
) -> QuoteDetailResponse:
    """Retrieve full quote details for the authenticated customer."""
    return await quote_service.get_quote_by_id(id, current_user)
