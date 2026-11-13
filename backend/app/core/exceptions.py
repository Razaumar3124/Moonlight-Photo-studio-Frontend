from typing import Any

from fastapi import status


class AppException(Exception):
    """Base application exception supporting standard error envelope fields."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
        internal_detail: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []
        self.headers = headers or {}
        # Diagnostic text for server logs only. Never serialised into API responses.
        self.internal_detail = internal_detail


class DatabaseUnavailableException(AppException):
    """Raised when the database connection fails or times out."""

    def __init__(
        self,
        message: str = "Database service is currently unreachable",
        issue: str = "MongoDB ping timed out or connection failed",
    ):
        # `issue` may contain driver/host details: logged, never returned to clients.
        super().__init__(
            message=message,
            code="DATABASE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=[{"field": "database", "issue": "Database is temporarily unavailable"}],
            internal_detail=issue,
        )


class ResourceNotFoundException(AppException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = "Requested resource was not found", field: str = "id"):
        super().__init__(
            message=message,
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=[{"field": field, "issue": message}],
        )


class ValidationException(AppException):
    """Raised for manual business logic validation failures."""

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details or [],
        )


class AccountAlreadyExistsException(AppException):
    """Raised when attempting to register with an already-used email or phone."""

    def __init__(self, field: str, issue: str):
        super().__init__(
            message="An account with this email or mobile number already exists.",
            code="ACCOUNT_ALREADY_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
            details=[{"field": field, "issue": issue}],
        )


class IdempotencyConflictException(AppException):
    """Raised when an Idempotency-Key is reused for a different request, or has expired."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="IDEMPOTENCY_KEY_REUSED",
            status_code=status.HTTP_409_CONFLICT,
            details=[{"field": "Idempotency-Key", "issue": "Key already used for another request"}],
        )


class PhotoInUseException(AppException):
    """Raised when deleting a photo that saved designs still use."""

    def __init__(self, designs_count: int):
        noun = "design" if designs_count == 1 else "designs"
        super().__init__(
            message=(
                f"This photo is used in {designs_count} saved {noun}. "
                "Remove it from those designs before deleting it."
            ),
            code="PHOTO_IN_USE",
            status_code=status.HTTP_409_CONFLICT,
            details=[{"field": "id", "issue": f"Used in {designs_count} saved {noun}"}],
        )


class InvalidCredentialsException(AppException):
    """Raised when credentials do not match records (deliberately non-enumerating)."""

    def __init__(
        self,
        message: str = "Those details don’t match our records. Check them and try again.",
    ):
        super().__init__(
            message=message,
            code="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=[],
        )


class AccountDisabledException(AppException):
    """Raised when attempting to authenticate with a deactivated account."""

    def __init__(
        self,
        message: str = "This account has been deactivated. Please contact support.",
    ):
        super().__init__(
            message=message,
            code="ACCOUNT_DISABLED",
            status_code=status.HTTP_403_FORBIDDEN,
            details=[],
        )


class InvalidTokenException(AppException):
    """Raised when an access or refresh token is malformed, invalid, or forged."""

    def __init__(self, message: str = "Invalid or malformed authentication token."):
        super().__init__(
            message=message,
            code="INVALID_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=[],
        )


class TokenExpiredException(AppException):
    """Raised when an access or refresh token has expired."""

    def __init__(self, message: str = "Authentication token has expired. Please log in again."):
        super().__init__(
            message=message,
            code="TOKEN_EXPIRED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=[],
        )


class TokenRevokedException(AppException):
    """Raised when a refresh token has been revoked or re-used."""

    def __init__(self, message: str = "Session has been revoked or expired. Please sign in again."):
        super().__init__(
            message=message,
            code="TOKEN_REVOKED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=[],
        )


class InvalidGoogleTokenException(AppException):
    """Raised when Google ID token fails cryptographic verification."""

    def __init__(self, message: str = "Google authentication token could not be verified."):
        super().__init__(
            message=message,
            code="INVALID_GOOGLE_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=[],
        )


class CsrfValidationException(AppException):
    """Raised when a cookie-authenticated request fails CSRF checks."""

    def __init__(self, message: str = "Request blocked by CSRF protection."):
        super().__init__(
            message=message,
            code="CSRF_VALIDATION_FAILED",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class PayloadTooLargeException(AppException):
    """Raised when a request body or uploaded file exceeds its size limit."""

    def __init__(self, message: str = "The request is too large.", field: str = "body"):
        super().__init__(
            message=message,
            code="PAYLOAD_TOO_LARGE",
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            details=[{"field": field, "issue": message}],
        )


class GoogleAuthNotConfiguredException(AppException):
    """Raised when Google sign-in is attempted but GOOGLE_CLIENT_ID is not configured.

    Without a client ID the token audience can't be checked, so ID tokens issued to any
    other Google application would be accepted. Fail closed instead.
    """

    def __init__(self, message: str = "Google sign-in is not available right now."):
        super().__init__(
            message=message,
            code="GOOGLE_AUTH_NOT_CONFIGURED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class RateLimitExceededException(AppException):
    """Raised when a client exceeds rate limits."""

    def __init__(
        self,
        message: str = "Too many attempts. Please wait a minute and try again.",
        retry_after_seconds: int | None = None,
    ):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=[],
            headers={"Retry-After": str(max(1, retry_after_seconds))}
            if retry_after_seconds is not None
            else None,
        )
        self.retry_after_seconds = retry_after_seconds


class RegistrationLimitException(RateLimitExceededException):
    """Raised when one network has created its daily allowance of new accounts."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            "Too many accounts were created from your network today. Please try again "
            "tomorrow or contact the studio.",
            retry_after_seconds=retry_after_seconds,
        )
        self.code = "REGISTRATION_LIMIT_REACHED"


class ForbiddenException(AppException):
    """Raised when an authenticated user attempts to access or mutate an unowned resource."""

    def __init__(
        self,
        message: str = "You do not have permission to access or modify this resource.",
        field: str = "id",
    ):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
            details=[{"field": field, "issue": message}],
        )


class StorageUnavailableException(AppException):
    """Raised when object storage (Cloudflare R2) is unreachable or fails."""

    def __init__(
        self,
        message: str = "Storage service is currently unavailable. Please try again later.",
        issue: str = "R2 storage operation timed out or failed",
    ):
        # `issue` may contain bucket names, keys or SDK errors: logged, never returned.
        super().__init__(
            message=message,
            code="STORAGE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=[{"field": "storage", "issue": "Storage is temporarily unavailable"}],
            internal_detail=issue,
        )


class StorageLimitReachedException(AppException):
    """Raised when accepting an upload would push stored data past the free-tier ceiling."""

    def __init__(self) -> None:
        super().__init__(
            message=(
                "Photo storage is full right now, so we can't accept new uploads. "
                "Please contact the studio."
            ),
            code="STORAGE_LIMIT_REACHED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=[{"field": "storage", "issue": "Storage capacity reached"}],
            headers={"Retry-After": "3600"},
        )


class EmailLimitReachedException(AppException):
    """Raised when today's email allowance is used up (same answer for every address)."""

    def __init__(self) -> None:
        super().__init__(
            message=(
                "Password reset emails are unavailable right now because the daily sending "
                "limit was reached. Please try again tomorrow or contact the studio."
            ),
            code="EMAIL_DAILY_LIMIT_REACHED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=[{"field": "email", "issue": "Daily email limit reached"}],
            headers={"Retry-After": "3600"},
        )
