import logging
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app.core.config import get_settings
from app.core.exceptions import (
    AccountAlreadyExistsException,
    AccountDisabledException,
    InvalidCredentialsException,
    InvalidTokenException,
    RateLimitExceededException,
    ValidationException,
)
from app.core.security import (
    generate_otp,
    generate_reset_token,
    hash_otp,
    hash_password,
    hash_token,
    verify_otp_hash,
    verify_password,
)
from app.models.session import PasswordResetInDB
from app.models.user import UserInDB
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.schemas.user import UserOut
from app.services.email_service import EmailService
from app.services.email_service import email_service as global_email_service
from app.services.rate_limiter import rate_limiter
from app.services.token_service import TokenService

logger = logging.getLogger("saf_studio.auth")


class AuthService:
    """Core domain service for user registration, authentication, and password recovery."""

    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        token_service: TokenService,
        email_service: EmailService | None = None,
    ) -> None:
        self.user_repo = user_repo
        self.session_repo = session_repo
        self.token_service = token_service
        self.email_service = email_service or global_email_service

    async def register_user(
        self,
        req: RegisterRequest,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthResponse:
        """Register a new customer account with Argon2id password hashing."""
        settings = get_settings()

        # Rate limiting by IP address
        rate_key = f"reg:{ip_address or 'unknown'}"
        rate_limiter.check_rate_limit(
            key=rate_key,
            max_attempts=settings.RATE_LIMIT_REGISTER_MAX_ATTEMPTS,
            window_seconds=settings.RATE_LIMIT_REGISTER_WINDOW_SECONDS,
        )

        # Check existing email
        existing_email = await self.user_repo.get_by_email(req.email)
        if existing_email:
            raise AccountAlreadyExistsException(field="email", issue="Email is already registered")

        # Check existing phone
        existing_phone = await self.user_repo.get_by_phone(req.phone)
        if existing_phone:
            raise AccountAlreadyExistsException(
                field="phone", issue="Mobile number is already registered"
            )

        # Hash password using Argon2id
        hashed_pwd = hash_password(req.password)
        now = datetime.now(UTC)

        user_doc = UserInDB(
            _id=str(ObjectId()),
            email=req.email,
            phone=req.phone,
            password_hash=hashed_pwd,
            full_name=req.full_name,
            role="customer",
            is_active=True,
            auth_provider="local",
            google_id=None,
            created_at=now,
            updated_at=now,
        )

        created_user = await self.user_repo.create(user_doc)

        # Issue access & refresh tokens
        tokens = await self.token_service.create_session(
            user_id=created_user.id,
            role=created_user.role,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        user_out = UserOut(
            id=created_user.id,
            email=created_user.email,
            full_name=created_user.full_name,
            phone=created_user.phone,
            role=created_user.role,
            is_active=created_user.is_active,
            created_at=created_user.created_at.isoformat(),
        )

        logger.info("New user registered successfully: id=%s", created_user.id)
        return AuthResponse(user=user_out, tokens=tokens)

    async def authenticate_user(
        self,
        req: LoginRequest,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthResponse:
        """Authenticate user by email or Indian phone and issue credentials."""
        settings = get_settings()

        # Identifier rate limiting to prevent brute-force attacks
        rate_identifier = req.email or req.phone or ip_address or "unknown"
        rate_key = f"login:{rate_identifier}"
        rate_limiter.check_rate_limit(
            key=rate_key,
            max_attempts=settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS,
            window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
        )

        # Retrieve user record by normalized email or phone
        user: UserInDB | None = None
        if req.email:
            user = await self.user_repo.get_by_email(req.email)
        elif req.phone:
            user = await self.user_repo.get_by_phone(req.phone)

        # Constant-time security check: if user doesn't exist,
        # run dummy verify to prevent timing attacks
        if not user or not user.password_hash:
            # Perform dummy Argon2id check to normalize timing
            verify_password("dummy_password", "$argon2id$v=19$m=65536,t=3,p=4$dummy$dummy")
            raise InvalidCredentialsException()

        # Verify password hash
        if not verify_password(req.password, user.password_hash):
            raise InvalidCredentialsException()

        # Check account active status
        if not user.is_active:
            raise AccountDisabledException()

        # Clear rate limiter on successful authentication
        rate_limiter.reset(rate_key)

        # Update last login timestamp
        await self.user_repo.update_last_login(user.id)

        # Issue access & refresh tokens
        tokens = await self.token_service.create_session(
            user_id=user.id,
            role=user.role,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        user_out = UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
        )

        logger.info("User authenticated successfully: id=%s", user.id)
        return AuthResponse(user=user_out, tokens=tokens)

    async def request_password_reset_otp(
        self,
        req: ForgotPasswordRequest,
        ip_address: str | None = None,
    ) -> ForgotPasswordResponse:
        """Step 1: Request Email OTP for password recovery with rate limits and 60s cooldown."""
        settings = get_settings()

        # 1. Enforce sliding window rate limits (IP and Email)
        rate_key_ip = f"forgot_pwd_ip:{ip_address or 'unknown'}"
        rate_limiter.check_rate_limit(
            rate_key_ip,
            settings.RATE_LIMIT_FORGOT_PASSWORD_IP_MAX_ATTEMPTS,
            settings.RATE_LIMIT_FORGOT_PASSWORD_IP_WINDOW_SECONDS,
        )

        rate_key_email = f"forgot_pwd_email:{req.email}"
        rate_limiter.check_rate_limit(
            rate_key_email,
            settings.RATE_LIMIT_FORGOT_PASSWORD_MAX_ATTEMPTS,
            settings.RATE_LIMIT_FORGOT_PASSWORD_WINDOW_SECONDS,
        )

        # 2. Check 60-second database-backed cooldown across instances
        active_otp = await self.session_repo.get_active_otp(req.email)
        now = datetime.now(UTC)
        if active_otp and active_otp.resend_available_at and active_otp.resend_available_at > now:
            remaining = int((active_otp.resend_available_at - now).total_seconds()) + 1
            raise RateLimitExceededException(
                f"Please wait {remaining} seconds before requesting another verification code."
            )

        # 3. Lookup user; if active, generate OTP and dispatch email
        user = await self.user_repo.get_by_email(req.email)
        if user and user.is_active:
            # Invalidate any prior active OTP challenge for this email
            await self.session_repo.invalidate_active_otps(req.email)

            otp_code = generate_otp()
            otp_hash = hash_otp(req.email, otp_code)
            expires_at = now + timedelta(minutes=settings.EMAIL_OTP_EXPIRE_MINUTES)
            resend_available_at = now + timedelta(seconds=settings.EMAIL_OTP_COOLDOWN_SECONDS)

            otp_doc = PasswordResetInDB(
                _id=str(ObjectId()),
                user_id=user.id,
                email=req.email,
                token_hash=otp_hash,
                purpose="email_otp",
                attempts=0,
                max_attempts=settings.OTP_MAX_ATTEMPTS,
                resend_available_at=resend_available_at,
                expires_at=expires_at,
                used=False,
                created_at=now,
            )
            await self.session_repo.create_password_reset(otp_doc)

            # Dispatch branded email via EmailService
            await self.email_service.send_otp_email(
                to_email=req.email,
                otp_code=otp_code,
                expiry_minutes=settings.EMAIL_OTP_EXPIRE_MINUTES,
            )
            logger.info("Password reset OTP generated and dispatched for user_id=%s", user.id)

        # Return non-enumerating generic response regardless of whether account exists
        return ForgotPasswordResponse(
            message="If an account is associated with this email, a verification code was sent.",
            cooldown_seconds=settings.EMAIL_OTP_COOLDOWN_SECONDS,
        )

    async def initiate_password_recovery(
        self,
        req: ForgotPasswordRequest,
        ip_address: str | None = None,
    ) -> ForgotPasswordResponse:
        """Alias for request_password_reset_otp to maintain backward compatibility."""
        return await self.request_password_reset_otp(req, ip_address=ip_address)

    async def verify_password_reset_otp(
        self,
        req: VerifyOtpRequest,
        ip_address: str | None = None,
    ) -> VerifyOtpResponse:
        """Step 2: Verify 6-digit OTP in constant time and issue reset authorization token."""
        # Rate limit verification attempts to mitigate brute-force
        rate_key = f"verify_otp_ip:{ip_address or 'unknown'}"
        rate_limiter.check_rate_limit(rate_key, max_attempts=15, window_seconds=300)

        active_otp = await self.session_repo.get_active_otp(req.email)
        if not active_otp:
            raise ValidationException(
                message="Verification code has expired or is invalid. Please request a new code.",
                details=[{"field": "otp", "issue": "Code expired or not found"}],
            )

        if active_otp.attempts >= active_otp.max_attempts:
            raise ValidationException(
                message="Maximum verification attempts exceeded. Please request a new code.",
                details=[{"field": "otp", "issue": "Max attempts exceeded"}],
            )

        is_valid = verify_otp_hash(req.email, req.otp, active_otp.token_hash)
        if not is_valid:
            new_attempts = await self.session_repo.increment_otp_attempts(active_otp.id)
            remaining = max(0, active_otp.max_attempts - new_attempts)
            if remaining == 0:
                raise ValidationException(
                    message="Maximum verification attempts exceeded. Please request a new code.",
                    details=[
                        {"field": "otp", "issue": "Account recovery locked. Request new code."}
                    ],
                )
            raise ValidationException(
                message=f"Incorrect verification code. {remaining} attempt(s) remaining.",
                details=[{"field": "otp", "issue": f"Invalid code. {remaining} attempt(s) left."}],
            )

        # Atomically consume the OTP so it cannot be verified twice
        consumed = await self.session_repo.consume_otp_atomically(active_otp.id)
        if not consumed:
            raise ValidationException(
                message="Verification code has already been used. Please request a new code.",
                details=[{"field": "otp", "issue": "Code already redeemed"}],
            )

        # Issue an ephemeral, single-use reset authorization token valid for 10 minutes
        raw_reset_token = generate_reset_token()
        token_hash = hash_token(raw_reset_token)
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=10)

        reset_session_doc = PasswordResetInDB(
            _id=str(ObjectId()),
            user_id=active_otp.user_id,
            email=req.email,
            token_hash=token_hash,
            purpose="password_reset_session",
            expires_at=expires_at,
            used=False,
            created_at=now,
        )
        await self.session_repo.create_password_reset(reset_session_doc)
        logger.info(
            "OTP verified successfully for user_id=%s. Issued password reset session token.",
            active_otp.user_id,
        )

        return VerifyOtpResponse(
            reset_token=raw_reset_token,
            expires_in_seconds=600,
        )

    async def reset_password_with_token(
        self,
        req: ResetPasswordRequest,
    ) -> ResetPasswordResponse:
        """Step 3: Atomically consume reset session token and update user credentials."""
        token_hash = hash_token(req.reset_token)

        # Atomically validate, check expiry, and consume the reset session token
        session_doc = await self.session_repo.consume_reset_session_atomically(token_hash)
        if not session_doc:
            raise InvalidTokenException(
                "Password reset session has expired or is invalid. Please restart recovery."
            )

        user = await self.user_repo.get_by_id(session_doc.user_id)
        if not user or not user.is_active:
            raise InvalidTokenException(
                "User associated with password reset session is not found or inactive."
            )

        # Prevent reusing the existing password
        if user.password_hash and verify_password(req.new_password, user.password_hash):
            raise ValidationException(
                message="New password cannot be the same as your previous password.",
                details=[{"field": "new_password", "issue": "Cannot reuse current password"}],
            )

        # Hash with Argon2id and update user credentials
        new_password_hash = hash_password(req.new_password)
        await self.user_repo.update_password(user.id, new_password_hash)

        # Revoke all active user refresh sessions (compromise protection)
        await self.session_repo.revoke_all_user_tokens(user.id)
        logger.info("Password reset executed and active sessions revoked for user_id=%s", user.id)

        return ResetPasswordResponse(
            message=(
                "Your password has been successfully reset. Please sign in with your new password."
            )
        )
