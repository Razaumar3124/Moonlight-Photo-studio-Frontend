from fastapi import APIRouter, Cookie, Request, Response, status

from app.api.dependencies import (
    AuthServiceDep,
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
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.schemas.common import ApiErrorResponse
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


def _set_refresh_cookie(response: Response, refresh_token: str, settings: Settings) -> None:
    """Set secure httpOnly refresh token cookie on HTTP response."""
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
        path="/api/v1/auth",
    )


def _delete_refresh_cookie(response: Response, settings: Settings) -> None:
    """Clear refresh token cookie on logout."""
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path="/api/v1/auth",
        httponly=True,
        secure=settings.effective_cookie_secure,
        samesite=settings.COOKIE_SAMESITE,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ApiErrorResponse,
            "description": "Email or phone already exists",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
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
        "Returns JWT access token and sets httpOnly refresh cookie."
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
    user_agent = request.headers.get("user-agent")
    client_ip = get_client_ip(request)

    result = await auth_service.register_user(req, user_agent=user_agent, ip_address=client_ip)
    _set_refresh_cookie(response, result.tokens.refresh_token, settings)
    return result


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Invalid credentials",
        },
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorResponse, "description": "Account disabled"},
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ApiErrorResponse,
            "description": "Too many failed attempts",
        },
    },
    summary="Authenticate using email or phone",
    description=(
        "Authenticates customer by email or Indian phone and password. "
        "Returns JWT access token and sets httpOnly refresh cookie."
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
    user_agent = request.headers.get("user-agent")
    client_ip = get_client_ip(request)

    result = await auth_service.authenticate_user(req, user_agent=user_agent, ip_address=client_ip)
    _set_refresh_cookie(response, result.tokens.refresh_token, settings)
    return result


@router.post(
    "/refresh",
    response_model=AuthTokens,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Invalid, expired, or revoked token",
        },
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorResponse, "description": "Account disabled"},
    },
    summary="Securely refresh an access token",
    description=(
        "Rotates refresh token and issues fresh JWT access token. "
        "Reads refresh token from cookie or request body."
    ),
)
async def refresh_tokens(
    request: Request,
    response: Response,
    token_service: TokenServiceDep,
    settings: SettingsDep,
    body: RefreshTokenRequest | None = None,
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
) -> AuthTokens:
    """EP-AUTH-04: Session refresh with rotation and reuse detection."""
    raw_token = (
        body.refresh_token if body and body.refresh_token else None
    ) or refresh_token_cookie
    if not raw_token:
        raise InvalidTokenException("Missing refresh token in cookie or request body.")

    user_agent = request.headers.get("user-agent")
    client_ip = get_client_ip(request)

    new_tokens = await token_service.rotate_refresh_token(
        raw_refresh_token=raw_token,
        user_agent=user_agent,
        ip_address=client_ip,
    )
    _set_refresh_cookie(response, new_tokens.refresh_token, settings)
    return new_tokens


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current session",
    description=(
        "Revokes the active refresh token session in database and clears the refresh cookie."
    ),
)
async def logout(
    response: Response,
    token_service: TokenServiceDep,
    settings: SettingsDep,
    body: RefreshTokenRequest | None = None,
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
) -> None:
    """EP-AUTH-05: Session logout and revocation."""
    raw_token = (
        body.refresh_token if body and body.refresh_token else None
    ) or refresh_token_cookie
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
    summary="Initiate email OTP password recovery",
    description=(
        "Initiates password recovery for the given email address. Deliberately non-enumerating."
    ),
)
async def forgot_password(
    req: ForgotPasswordRequest,
    request: Request,
    auth_service: AuthServiceDep,
) -> ForgotPasswordResponse:
    """EP-AUTH-06: Step 1 - Password recovery initiation and email OTP dispatch."""
    client_ip = get_client_ip(request)
    return await auth_service.request_password_reset_otp(req, ip_address=client_ip)


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
        status.HTTP_400_BAD_REQUEST: {
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
    client_ip = get_client_ip(request)
    return await auth_service.verify_password_reset_otp(req, ip_address=client_ip)


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
        status.HTTP_400_BAD_REQUEST: {
            "model": ApiErrorResponse,
            "description": "Invalid password policy or password reuse",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Invalid or expired reset session token",
        },
    },
)
async def reset_password(
    req: ResetPasswordRequest,
    auth_service: AuthServiceDep,
) -> ResetPasswordResponse:
    """EP-AUTH-08: Step 3 - Update account password using single-use reset token."""
    return await auth_service.reset_password_with_token(req)


@router.post(
    "/google",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Invalid Google token",
        },
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorResponse, "description": "Account disabled"},
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
    """EP-AUTH-07: Google OpenID Connect authentication."""
    user_agent = request.headers.get("user-agent")
    client_ip = get_client_ip(request)

    result = await google_service.authenticate_with_google(
        id_token_str=req.id_token,
        user_agent=user_agent,
        ip_address=client_ip,
    )
    _set_refresh_cookie(response, result.tokens.refresh_token, settings)
    return result
