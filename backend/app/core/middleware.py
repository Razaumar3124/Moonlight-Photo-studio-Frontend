"""ASGI middleware: request body limits and security response headers."""

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from starlette import status
from starlette.exceptions import HTTPException

from app.core import limits
from app.core.config import get_settings

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

# Room for multipart boundaries and part headers around an uploaded file.
_MULTIPART_OVERHEAD = 64 * 1024
_BODYLESS_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class RequestBodyTooLarge(HTTPException):
    """413 raised while the body streams in.

    It is an HTTPException on purpose: FastAPI re-raises those from body parsing (anything
    else becomes a generic 400), so the client gets 413 through the normal error envelope.
    """

    def __init__(self, limit: int) -> None:
        super().__init__(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Request body exceeds the {limit // 1024} KB limit for this endpoint.",
        )


def body_limit_for(path: str) -> int:
    """Byte limit for a request path: uploads get their file limit, everything else 1 MiB."""
    settings = get_settings()
    api = settings.API_V1_STR.rstrip("/")
    if path == f"{api}/photos/upload":
        return limits.PHOTO_MAX_BYTES + _MULTIPART_OVERHEAD
    if path == f"{api}/quotes/prepare":
        return (
            limits.QUOTE_PREVIEW_MAX_BYTES + settings.MAX_REQUEST_BODY_BYTES + _MULTIPART_OVERHEAD
        )
    return settings.MAX_REQUEST_BODY_BYTES


class BodySizeLimitMiddleware:
    """Reject oversized bodies before they are buffered.

    * A declared ``Content-Length`` above the limit is rejected immediately (413), before
      any of the body is read.
    * Bodies without a length (chunked) are counted as they stream; the request is aborted
      with 413 as soon as the limit is crossed. Only the parsed prefix was ever in memory
      (multipart files spool to disk after 1 MB).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method", "GET") in _BODYLESS_METHODS:
            await self.app(scope, receive, send)
            return

        limit = body_limit_for(scope.get("path", ""))
        declared = None
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                declared = value
                break
        if declared is not None:
            try:
                too_large = int(declared) > limit
            except ValueError:
                too_large = True  # malformed length: refuse rather than guess
            if too_large:
                await _send_error(scope, receive, send, RequestBodyTooLarge(limit))
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise RequestBodyTooLarge(limit)
            return message

        await self.app(scope, limited_receive, send)


async def _send_error(scope: Scope, receive: Receive, send: Send, exc: HTTPException) -> None:
    from app.core.handlers import create_error_response

    response = create_error_response(
        status_code=exc.status_code,
        code="PAYLOAD_TOO_LARGE",
        message=str(exc.detail),
        details=[{"field": "body", "issue": str(exc.detail)}],
    )
    response.headers["Connection"] = "close"
    await response(scope, receive, send)


_BASE_SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
]
# JSON and media responses never need to load anything or be framed.
_API_CSP = b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class SecurityHeadersMiddleware:
    """Add security headers to every response unless the route already set them.

    * ``Content-Security-Policy`` defaults to a deny-all API policy; HTML routes (the shared
      quote report) set their own.
    * ``Cache-Control: no-store`` on ``/auth/*`` so tokens and profiles are never cached.
    * ``Strict-Transport-Security`` in production.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        path = scope.get("path", "")
        is_auth = path.startswith(f"{settings.API_V1_STR.rstrip('/')}/auth")
        hsts = settings.is_production

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                extra = [h for h in _BASE_SECURITY_HEADERS if h[0] not in present]
                if b"content-security-policy" not in present and not _is_docs(path):
                    extra.append((b"content-security-policy", _API_CSP))
                if is_auth and b"cache-control" not in present:
                    extra.append((b"cache-control", b"no-store"))
                if hsts and b"strict-transport-security" not in present:
                    extra.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = headers + extra
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _is_docs(path: str) -> bool:
    # Swagger UI / ReDoc (development only) load scripts and styles from a CDN.
    return path in ("/docs", "/redoc", "/docs/oauth2-redirect")
