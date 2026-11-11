import uuid
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app.core.config import get_settings
from app.core.exceptions import (
    AccountDisabledException,
    InvalidTokenException,
    TokenExpiredException,
    TokenRevokedException,
)
from app.core.security import (
    create_access_token,
    generate_secure_token,
    hash_token,
)
from app.models.session import RefreshTokenInDB
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthTokens


class TokenService:
    """Manages token issuance, cryptographic verification, rotation, and revocation."""

    def __init__(self, session_repo: SessionRepository, user_repo: UserRepository) -> None:
        self.session_repo = session_repo
        self.user_repo = user_repo

    async def create_session(
        self,
        user_id: str,
        role: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthTokens:
        """Issue a fresh access/refresh token pair and record the session."""
        settings = get_settings()

        access_token, expires_in = create_access_token(subject=user_id, role=role)
        raw_refresh_token = generate_secure_token()
        refresh_hash = hash_token(raw_refresh_token)
        family_id = str(uuid.uuid4())

        now = datetime.now(UTC)
        expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        session_doc = RefreshTokenInDB(
            _id=str(ObjectId()),
            user_id=user_id,
            token_hash=refresh_hash,
            family_id=family_id,
            is_revoked=False,
            replaced_by=None,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
            created_at=now,
        )
        await self.session_repo.create_refresh_token(session_doc)

        return AuthTokens(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    async def rotate_refresh_token(
        self,
        raw_refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthTokens:
        """Rotate an active refresh token: revoke current, issue successor in same family."""
        if not raw_refresh_token:
            raise InvalidTokenException("Missing refresh token.")

        settings = get_settings()
        token_hash = hash_token(raw_refresh_token)
        session = await self.session_repo.get_refresh_token_by_hash(token_hash)

        if not session:
            raise InvalidTokenException("Invalid refresh token.")

        # REUSE DETECTION: If token was already revoked, a replay attack is occurring
        if session.is_revoked:
            # Compromise response: Revoke all tokens in this family immediately
            await self.session_repo.revoke_family(session.family_id)
            raise TokenRevokedException(
                "Refresh token reuse detected. "
                "All sessions in this chain have been revoked for security."
            )

        now = datetime.now(UTC)
        # Ensure session.expires_at is timezone-aware for comparison
        expires_at = (
            session.expires_at
            if session.expires_at.tzinfo
            else session.expires_at.replace(tzinfo=UTC)
        )
        if expires_at < now:
            await self.session_repo.revoke_refresh_token(session.id)
            raise TokenExpiredException("Refresh token has expired. Please log in again.")

        # Verify user is still active
        user = await self.user_repo.get_by_id(session.user_id)
        if not user or not user.is_active:
            await self.session_repo.revoke_family(session.family_id)
            raise AccountDisabledException()

        # Generate successor token in the same family
        new_raw_refresh = generate_secure_token()
        new_refresh_hash = hash_token(new_raw_refresh)
        new_session_id = str(ObjectId())

        new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        successor_doc = RefreshTokenInDB(
            _id=new_session_id,
            user_id=session.user_id,
            token_hash=new_refresh_hash,
            family_id=session.family_id,
            is_revoked=False,
            replaced_by=None,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=new_expires_at,
            created_at=now,
        )
        await self.session_repo.create_refresh_token(successor_doc)

        # Mark previous token as revoked and track successor
        await self.session_repo.revoke_refresh_token(session.id, replaced_by=new_session_id)

        # Generate fresh access token
        access_token, expires_in = create_access_token(subject=user.id, role=user.role)

        return AuthTokens(
            access_token=access_token,
            refresh_token=new_raw_refresh,
            token_type="bearer",
            expires_in=expires_in,
        )

    async def revoke_token(self, raw_refresh_token: str) -> None:
        """Revoke a refresh token on user logout."""
        if not raw_refresh_token:
            return
        token_hash = hash_token(raw_refresh_token)
        session = await self.session_repo.get_refresh_token_by_hash(token_hash)
        if session:
            await self.session_repo.revoke_refresh_token(session.id)
