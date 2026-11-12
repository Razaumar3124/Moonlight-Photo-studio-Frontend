import logging
import uuid
from dataclasses import dataclass
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

logger = logging.getLogger("moonlight_studio.tokens")


@dataclass(frozen=True)
class IssuedTokens:
    """Tokens produced by the service layer.

    Only ``public`` is ever serialised. The refresh token goes into the httpOnly cookie and
    is ``None`` when a concurrent refresh already rotated the session (the browser keeps the
    cookie set by the winning request).
    """

    access_token: str
    expires_in: int
    refresh_token: str | None

    @property
    def public(self) -> AuthTokens:
        return AuthTokens(access_token=self.access_token, expires_in=self.expires_in)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class TokenService:
    """Manages token issuance, cryptographic verification, rotation, and revocation."""

    def __init__(self, session_repo: SessionRepository, user_repo: UserRepository) -> None:
        self.session_repo = session_repo
        self.user_repo = user_repo

    async def _store_refresh_token(
        self,
        user_id: str,
        family_id: str,
        user_agent: str | None,
        ip_address: str | None,
        now: datetime,
    ) -> tuple[str, str]:
        """Persist a new refresh token (hash only). Returns (raw_token, record_id)."""
        settings = get_settings()
        raw_refresh_token = generate_secure_token()
        record_id = str(ObjectId())
        await self.session_repo.create_refresh_token(
            RefreshTokenInDB(
                _id=record_id,
                user_id=user_id,
                token_hash=hash_token(raw_refresh_token),
                family_id=family_id,
                is_revoked=False,
                replaced_by=None,
                user_agent=(user_agent or "")[:256] or None,
                ip_address=ip_address,
                expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                created_at=now,
            )
        )
        return raw_refresh_token, record_id

    async def create_session(
        self,
        user_id: str,
        role: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> IssuedTokens:
        """Issue a fresh access/refresh token pair and record the session."""
        access_token, expires_in = create_access_token(subject=user_id, role=role)
        raw_refresh, _ = await self._store_refresh_token(
            user_id, str(uuid.uuid4()), user_agent, ip_address, datetime.now(UTC)
        )
        return IssuedTokens(access_token, expires_in, raw_refresh)

    async def rotate_refresh_token(
        self,
        raw_refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> IssuedTokens:
        """Rotate a refresh token: atomically retire it and issue a successor in its family.

        * The claim is a single conditional update, so of several concurrent requests with
          the same token exactly one rotates it.
        * A request that loses that race within REFRESH_REUSE_GRACE_SECONDS (another tab,
          a retried request) gets a fresh access token but no new refresh token; the session
          family stays intact.
        * Presenting a token that was rotated longer ago, or revoked for any other reason,
          is treated as theft: the whole family is revoked.
        """
        if not raw_refresh_token:
            raise InvalidTokenException("Missing refresh token.")

        settings = get_settings()
        now = datetime.now(UTC)
        token_hash = hash_token(raw_refresh_token)

        session = await self.session_repo.claim_refresh_token(token_hash, now)
        if session is None:
            return await self._handle_unclaimable_token(token_hash, now, settings)

        user = await self.user_repo.get_by_id(session.user_id)
        if not user or not user.is_active:
            await self.session_repo.revoke_family(session.family_id, reason="account_disabled")
            raise AccountDisabledException()

        new_raw_refresh, successor_id = await self._store_refresh_token(
            user.id, session.family_id, user_agent, ip_address, now
        )
        await self.session_repo.set_replaced_by(session.id, successor_id)

        access_token, expires_in = create_access_token(subject=user.id, role=user.role)
        return IssuedTokens(access_token, expires_in, new_raw_refresh)

    async def _handle_unclaimable_token(
        self, token_hash: str, now: datetime, settings
    ) -> IssuedTokens:
        existing = await self.session_repo.get_refresh_token_by_hash(token_hash)
        if not existing:
            raise InvalidTokenException("Invalid refresh token.")

        if not existing.is_revoked:
            # Not revoked but not claimable: it has expired.
            await self.session_repo.revoke_refresh_token(existing.id, reason="expired")
            raise TokenExpiredException("Refresh token has expired. Please log in again.")

        grace = timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS)
        if (
            existing.revoked_reason == "rotated"
            and existing.revoked_at is not None
            and now - _aware(existing.revoked_at) <= grace
        ):
            user = await self.user_repo.get_by_id(existing.user_id)
            if not user or not user.is_active:
                raise AccountDisabledException()
            logger.info("Concurrent refresh within grace window: family=%s", existing.family_id)
            access_token, expires_in = create_access_token(subject=user.id, role=user.role)
            return IssuedTokens(access_token, expires_in, None)

        # Replay of a retired token: assume it was stolen and end every session in the chain.
        await self.session_repo.revoke_family(existing.family_id, reason="reuse_detected")
        logger.warning("Refresh token reuse detected: family=%s revoked", existing.family_id)
        raise TokenRevokedException(
            "Refresh token reuse detected. All sessions in this chain have been revoked."
        )

    async def revoke_token(self, raw_refresh_token: str) -> None:
        """Revoke a refresh token on user logout."""
        if not raw_refresh_token:
            return
        session = await self.session_repo.get_refresh_token_by_hash(hash_token(raw_refresh_token))
        if session:
            await self.session_repo.revoke_refresh_token(session.id, reason="logout")
