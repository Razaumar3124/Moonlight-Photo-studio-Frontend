import logging
from datetime import UTC, datetime

from bson import ObjectId
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings
from app.core.exceptions import (
    AccountDisabledException,
    InvalidGoogleTokenException,
)
from app.models.user import UserInDB
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthResponse
from app.schemas.user import UserOut
from app.services.token_service import TokenService

logger = logging.getLogger("saf_studio.google_auth")


class GoogleAuthService:
    """Official Google OpenID Connect ID token verification and user linking."""

    def __init__(self, user_repo: UserRepository, token_service: TokenService) -> None:
        self.user_repo = user_repo
        self.token_service = token_service

    async def authenticate_with_google(
        self,
        id_token_str: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthResponse:
        """Verify Google ID token and sign in / register user."""
        settings = get_settings()

        try:
            # Use Google's official id_token verification
            request = google_requests.Request()
            audience = settings.GOOGLE_CLIENT_ID or None

            id_info = google_id_token.verify_oauth2_token(
                id_token_str,
                request,
                audience=audience,
            )
        except Exception as exc:
            logger.warning("Google ID token verification failed: %s", exc)
            raise InvalidGoogleTokenException() from exc

        # Verify email status
        email = id_info.get("email")
        email_verified = id_info.get("email_verified", False)
        google_id = id_info.get("sub")
        full_name = id_info.get("name", "Google User")

        if not email or not email_verified or not google_id:
            logger.warning("Google token missing verified email or sub identifier")
            raise InvalidGoogleTokenException("Google account must have a verified email address.")

        email_clean = email.strip().lower()

        # 1. Lookup user by Google ID
        user = await self.user_repo.get_by_google_id(google_id)

        # 2. If not found by google_id, check by email
        if not user:
            user = await self.user_repo.get_by_email(email_clean)
            if user:
                if not user.is_active:
                    logger.warning("Cannot link Google ID to disabled account: user_id=%s", user.id)
                    raise AccountDisabledException()
                if user.google_id and user.google_id != google_id:
                    logger.warning("User %s already linked to a different Google ID", user.id)
                    raise InvalidGoogleTokenException(
                        "This account is already linked to a different Google account."
                    )
                # Link Google ID to existing verified email account
                await self.user_repo.link_google_id(user.id, google_id)
                user.google_id = google_id
                logger.info("Linked Google identity to existing account: user_id=%s", user.id)

        # 3. If user still does not exist, create new Google user
        if not user:
            now = datetime.now(UTC)
            new_user = UserInDB(
                _id=str(ObjectId()),
                email=email_clean,
                phone=None,
                password_hash=None,
                full_name=full_name,
                role="customer",
                is_active=True,
                auth_provider="google",
                google_id=google_id,
                created_at=now,
                updated_at=now,
            )
            user = await self.user_repo.create(new_user)
            logger.info("Registered new user via Google identity: user_id=%s", user.id)

        # Check account status
        if not user.is_active:
            raise AccountDisabledException()

        # Update last login
        await self.user_repo.update_last_login(user.id)

        # Create session and return AuthResponse
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

        return AuthResponse(user=user_out, tokens=tokens)
