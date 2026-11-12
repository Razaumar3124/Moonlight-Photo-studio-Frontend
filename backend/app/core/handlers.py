import logging
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.schemas.common import ApiErrorDetail, ApiErrorPayload, ApiErrorResponse

logger = logging.getLogger("moonlight_studio.errors")


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Construct a uniform JSONResponse conforming to ApiErrorResponse."""
    detail_objs = [
        ApiErrorDetail(field=d.get("field", ""), issue=d.get("issue", "")) for d in (details or [])
    ]
    payload = ApiErrorPayload(
        code=code,
        message=message,
        details=detail_objs,
        timestamp=datetime.now(UTC).isoformat(),
    )
    return JSONResponse(
        status_code=status_code,
        content=ApiErrorResponse(error=payload).model_dump(),
        headers=headers,
    )


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    if exc.internal_detail:
        logger.warning(
            "Application exception: code=%s, message=%s, internal=%s",
            exc.code,
            exc.message,
            exc.internal_detail,
        )
    else:
        logger.warning("Application exception: code=%s, message=%s", exc.code, exc.message)
    return create_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers=exc.headers or None,
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic schema validation failures with standard envelope."""
    details: list[dict[str, str]] = []
    for error in exc.errors():
        # Request field path without the source prefix: "email", "wall.width_inches",
        # "items.0.matting.color_id" (a top-level field keeps its plain name).
        loc = list(error.get("loc", []))
        if loc and loc[0] in ("body", "query", "path", "header", "cookie"):
            loc = loc[1:]
        field = ".".join(str(part) for part in loc)
        msg = str(error.get("msg", "Invalid value")).removeprefix("Value error, ")
        details.append({"field": field, "issue": msg})

    logger.info("Validation failed: %d errors", len(details))
    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="VALIDATION_ERROR",
        message="Invalid request parameters",
        details=details,
    )


async def http_exception_handler(
    _request: Request, exc: HTTPException | StarletteHTTPException
) -> JSONResponse:
    """Handle standard FastAPI/Starlette HTTP exceptions."""
    # Convert status codes to standard string codes
    code_map = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "ACCESS_DENIED",
        status.HTTP_404_NOT_FOUND: "RESOURCE_NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_413_CONTENT_TOO_LARGE: "PAYLOAD_TOO_LARGE",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMIT_EXCEEDED",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
        status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    message = str(exc.detail) if exc.detail else "An HTTP error occurred"

    logger.warning("HTTP %d error: %s", exc.status_code, message)
    return create_error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        details=[],
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions safely without leaking internal stack traces."""
    logger.exception("Unhandled server exception: %s", type(exc).__name__)
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal server error occurred",
        details=[],
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI app instance."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
