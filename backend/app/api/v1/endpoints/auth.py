"""Authentication endpoints.

Session model: the short-lived access token is returned in the JSON body (the frontend keeps
it in memory only); the refresh token is only ever an httpOnly, SameSite cookie scoped to
``REFRESH_COOKIE_PATH``. Every endpoint that sets or reads that cookie requires the
``X-CSRF-Protection: 1`` header (see ``require_csrf_protection``).
"""

from fastapi import APIRouter, BackgroundTasks, Request, Response, status

from app.api.dependencies import (
    AuthServiceDep,
    CsrfProtected,
    CurrentUserDep,
    GoogleAuthServiceDep,
    SettingsDep,
    TokenServiceDep,
)
from app.core.config import Settings
from app.core.exceptions import InvalidTokenException
from app.core.security import get_client_ip
from app.schemas.auth import (
    AuthResponse,
    AuthTokens,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleAuthRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.schemas.common import ApiErrorResponse
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])

_CSRF_RESPONSE = {
    status.HTTP_403_FORBIDDEN: {
        "model": ApiErrorResponse,
        "description": "CSRF_VALIDATION_FAILED: missing X-CSRF-Protection or bad Origin",
    }
}


def _set_refresh_cookie(response: Response, refresh_token: str, settings: Settings) -> None:
    """Set the httpOnly refresh-token cookie."""
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        secure=settings.effective_cookie_secure,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path=settings.refresh_cookie_path,
    )


def _delete_refresh_cookie(response: Response, settings: Settings) -> None:
    """Clear the refresh-token cookie (same attributes it was set with)."""
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path=settings.refresh_cookie_path,
        httponly=True,
        secure=settings.effective_cookie_secure,
        samesite=settings.COOKIE_SAMESITE,
    )


def _read_refresh_cookie(request: Request, settings: Settings) -> str | None:
    value = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    return value if value and len(value) <= 256 else None


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfProtected],
    responses={
        **_CSRF_RESPONSE,
        status.HTTP_409_CONFLICT: {
            "model": ApiErrorResponse,
            "description": "Email or phone already exists",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ApiErrorResponse,
            "description": "Validation failed",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ApiErrorResponse,
            "description": "Rate limit exceeded",
        },
    },
    summary="Register a new customer account",
    description=(
        "Registers user with full name, email, Indian mobile number, and password. "
        "Returns a JWT access token and sets the httpOnly refresh cookie."
    ),
)
async def register(
    req: RegisterRequest,
    request: Request,
    response: Response,
    auth_service: AuthServiceDep,
    settings: SettingsDep,
) -> AuthResponse:
    """EP-AUTH-01: User registration."""
    result = await auth_service.register_user(
        req, user_agent=request.headers.get("user-agent"), ip_address=get_client_ip(request)
    )
    _set_refresh_cookie(response, result.refresh_token, settings)
    return result.response


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[CsrfProtected],
    responses={
        **_CSRF_RESPONSE,
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Invalid credentials",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ApiErrorResponse,
            "description": "Too many attempts (per IP + account, per account, or per IP)",
        },
    },
    summary="Authenticate using email or phone",
    description=(
        "Authenticates customer by email or Indian phone and password. "
        "Returns a JWT access token and sets the httpOnly refresh cookie. "
        "A disabled account answers 403 ACCOUNT_DISABLED, but only after a correct password."
    ),
)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthServiceDep,
    settings: SettingsDep,
) -> AuthResponse:
    """EP-AUTH-02: User login."""
    result = await auth_service.authenticate_user(
        req, user_agent=request.headers.get("user-agent"), ip_address=get_client_ip(request)
    )
    _set_refresh_cookie(response, result.refresh_token, settings)
    return result.response


@router.post(
    "/refresh",
    response_model=AuthTokens,
    status_code=status.HTTP_200_OK,
    dependencies=[CsrfProtected],
    responses={
        **_CSRF_RESPONSE,
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Missing, invalid, expired, or revoked refresh cookie",
        },
    },
    summary="Refresh the access token",
    description=(
        "Rotates the refresh cookie and returns a new access token. The refresh token is read "
        "from the httpOnly cookie only. Concurrent refreshes (e.g. two tabs) are safe: the "
        "first rotates the cookie, the others receive an access token without a new cookie."
    ),
)
async def refresh_tokens(
    request: Request,
    response: Response,
    token_service: TokenServiceDep,
    settings: SettingsDep,
) -> AuthTokens:
    """EP-AUTH-04: Session refresh with atomic rotation and reuse detection."""
    raw_token = _read_refresh_cookie(request, settings)
    if not raw_token:
        raise InvalidTokenException("Missing refresh token cookie.")

    issued = await token_service.rotate_refresh_token(
        raw_refresh_token=raw_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    if issued.refresh_token:
        _set_refresh_cookie(response, issued.refresh_token, settings)
    return issued.public


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[CsrfProtected],
    responses=_CSRF_RESPONSE,
    summary="Revoke the current session",
    description="Revokes the refresh-token session in the database and clears the cookie.",
)
async def logout(
    request: Request,
    response: Response,
    token_service: TokenServiceDep,
    settings: SettingsDep,
) -> None:
    """EP-AUTH-05: Session logout and revocation."""
    raw_token = _read_refresh_cookie(request, settings)
    if raw_token:
        await token_service.revoke_token(raw_token)
    _delete_refresh_cookie(response, settings)


@router.get(
    "/me",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorResponse, "description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorResponse, "description": "Account disabled"},
    },
    summary="Retrieve current user profile",
    description=(
        "Returns profile information for the authenticated user based on the Bearer access token."
    ),
)
async def get_me(current_user: CurrentUserDep) -> UserOut:
    """EP-AUTH-03: Authenticated user profile."""
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ApiErrorResponse,
            "description": "Too many requests for this email or IP, or resend cooldown",
        },
    },
    summary="Initiate email OTP password recovery",
    description=(
        "Initiates password recovery for the given email address. Deliberately "
        "non-enumerating: the same response, without delay or errors from email delivery, "
        "whether or not the account exists."
    ),
)
async def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    auth_service: AuthServiceDep,
) -> ForgotPasswordResponse:
    """EP-AUTH-06: Step 1 - Password recovery initiation and email OTP dispatch."""
    return await auth_service.request_password_reset_otp(
        req, ip_address=get_client_ip(request), background_tasks=background_tasks
    )


@router.post(
    "/forgot-password/verify",
    response_model=VerifyOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify password recovery OTP",
    description=(
        "Verifies the 6-digit email OTP and issues a single-use "
        "temporary password reset session token."
    ),
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ApiErrorResponse,
            "description": "Invalid, expired, or locked OTP",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ApiErrorResponse,
            "description": "Too many verification attempts",
        },
    },
)
async def verify_forgot_password_otp(
    req: VerifyOtpRequest,
    request: Request,
    auth_service: AuthServiceDep,
) -> VerifyOtpResponse:
    """EP-AUTH-07: Step 2 - Verify OTP and receive temporary reset token."""
    return await auth_service.verify_password_reset_otp(req, ip_address=get_client_ip(request))


@router.post(
    "/forgot-password/reset",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset account password",
    description=(
        "Consumes the reset session token, validates the new password, "
        "updates credentials, and revokes active sessions."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Invalid or expired reset session token",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ApiErrorResponse,
            "description": "Invalid password policy or password reuse",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ApiErrorResponse,
            "description": "Too many reset attempts from this IP",
        },
    },
)
async def reset_password(
    req: ResetPasswordRequest,
    request: Request,
    auth_service: AuthServiceDep,
) -> ResetPasswordResponse:
    """EP-AUTH-08: Step 3 - Update account password using single-use reset token."""
    return await auth_service.reset_password_with_token(req, ip_address=get_client_ip(request))


@router.post(
    "/google",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[CsrfProtected],
    responses={
        **_CSRF_RESPONSE,
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Invalid Google token",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ApiErrorResponse,
            "description": "Google sign-in is not configured (GOOGLE_CLIENT_ID missing)",
        },
    },
    summary="Authenticate using Google identity",
    description=(
        "Cryptographically verifies Google OpenID Connect ID token and "
        "links or creates customer account."
    ),
)
async def google_auth(
    req: GoogleAuthRequest,
    request: Request,
    response: Response,
    google_service: GoogleAuthServiceDep,
    settings: SettingsDep,
) -> AuthResponse:
    """EP-AUTH-09: Google OpenID Connect authentication."""
    result = await google_service.authenticate_with_google(
        id_token_str=req.id_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    _set_refresh_cookie(response, result.refresh_token, settings)
    return result.response
