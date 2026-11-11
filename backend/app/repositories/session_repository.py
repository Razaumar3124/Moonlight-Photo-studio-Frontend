from datetime import UTC, datetime

from bson import ObjectId
from pymongo import ASCENDING, IndexModel, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from app.models.session import PasswordResetInDB, RefreshTokenInDB


class SessionRepository:
    """Data access repository for refresh_tokens and password_resets collections."""

    def __init__(self, db: AsyncDatabase) -> None:
        self.refresh_tokens: AsyncCollection = db["refresh_tokens"]
        self.password_resets: AsyncCollection = db["password_resets"]

    async def create_indexes(self) -> None:
        """Create unique and TTL indexes for session collections idempotently."""
        # Refresh tokens indexes
        refresh_indexes = [
            IndexModel(
                [("token_hash", ASCENDING)], unique=True, name="idx_refresh_token_hash_unique"
            ),
            IndexModel(
                [("user_id", ASCENDING), ("is_revoked", ASCENDING)],
                name="idx_refresh_user_revoked",
            ),
            IndexModel([("family_id", ASCENDING)], name="idx_refresh_family_id"),
            IndexModel(
                [("expires_at", ASCENDING)], expireAfterSeconds=0, name="idx_refresh_tokens_ttl"
            ),
        ]
        await self.refresh_tokens.create_indexes(refresh_indexes)

        # Password resets indexes
        reset_indexes = [
            IndexModel(
                [("token_hash", ASCENDING)], unique=True, name="idx_reset_token_hash_unique"
            ),
            IndexModel(
                [("expires_at", ASCENDING)], expireAfterSeconds=0, name="idx_password_resets_ttl"
            ),
            IndexModel(
                [("email", ASCENDING), ("purpose", ASCENDING), ("used", ASCENDING)],
                name="idx_resets_email_active",
            ),
        ]
        await self.password_resets.create_indexes(reset_indexes)

    async def create_refresh_token(self, token: RefreshTokenInDB) -> RefreshTokenInDB:
        """Persist a new refresh token record."""
        doc = token.model_dump(by_alias=True)
        doc["_id"] = ObjectId(token.id)
        doc["user_id"] = ObjectId(token.user_id)
        if token.replaced_by and ObjectId.is_valid(token.replaced_by):
            doc["replaced_by"] = ObjectId(token.replaced_by)

        await self.refresh_tokens.insert_one(doc)
        return token

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshTokenInDB | None:
        """Find a refresh token session by its SHA-256 hash."""
        doc = await self.refresh_tokens.find_one({"token_hash": token_hash})
        if not doc:
            return None
        return RefreshTokenInDB(
            _id=str(doc["_id"]),
            user_id=str(doc["user_id"]),
            token_hash=doc["token_hash"],
            family_id=doc["family_id"],
            is_revoked=doc.get("is_revoked", False),
            replaced_by=str(doc["replaced_by"]) if doc.get("replaced_by") else None,
            user_agent=doc.get("user_agent"),
            ip_address=doc.get("ip_address"),
            expires_at=doc["expires_at"],
            created_at=doc["created_at"],
        )

    async def revoke_refresh_token(self, token_id: str, replaced_by: str | None = None) -> None:
        """Mark a specific refresh token as revoked."""
        if not ObjectId.is_valid(token_id):
            return

        update_fields: dict = {"is_revoked": True}
        if replaced_by and ObjectId.is_valid(replaced_by):
            update_fields["replaced_by"] = ObjectId(replaced_by)

        await self.refresh_tokens.update_one(
            {"_id": ObjectId(token_id)},
            {"$set": update_fields},
        )

    async def revoke_family(self, family_id: str) -> None:
        """Revoke all tokens in a family chain upon reuse detection (compromise response)."""
        await self.refresh_tokens.update_many(
            {"family_id": family_id},
            {"$set": {"is_revoked": True}},
        )

    async def revoke_all_user_tokens(self, user_id: str) -> None:
        """Revoke all active sessions for a user (e.g. password change)."""
        if ObjectId.is_valid(user_id):
            await self.refresh_tokens.update_many(
                {"user_id": ObjectId(user_id)},
                {"$set": {"is_revoked": True}},
            )

    async def create_password_reset(self, reset: PasswordResetInDB) -> PasswordResetInDB:
        """Persist a password reset token record."""
        doc = reset.model_dump(by_alias=True)
        doc["_id"] = ObjectId(reset.id)
        doc["user_id"] = ObjectId(reset.user_id)
        await self.password_resets.insert_one(doc)
        return reset

    def _doc_to_password_reset(self, doc: dict) -> PasswordResetInDB:
        return PasswordResetInDB(
            _id=str(doc["_id"]),
            user_id=str(doc["user_id"]),
            email=doc.get("email"),
            token_hash=doc["token_hash"],
            purpose=doc.get("purpose", "password_reset"),
            attempts=doc.get("attempts", 0),
            max_attempts=doc.get("max_attempts", 3),
            resend_available_at=doc.get("resend_available_at"),
            expires_at=doc["expires_at"],
            used=doc.get("used", False),
            created_at=doc["created_at"],
        )

    async def get_password_reset_by_hash(self, token_hash: str) -> PasswordResetInDB | None:
        """Find a password reset token by its SHA-256 hash."""
        doc = await self.password_resets.find_one({"token_hash": token_hash})
        if not doc:
            return None
        return self._doc_to_password_reset(doc)

    async def get_active_otp(self, email: str) -> PasswordResetInDB | None:
        """Find active unexpired, unused email OTP challenge record."""
        now = datetime.now(UTC)
        doc = await self.password_resets.find_one(
            {
                "email": email.strip().lower(),
                "purpose": "email_otp",
                "used": False,
                "expires_at": {"$gt": now},
            }
        )
        return self._doc_to_password_reset(doc) if doc else None

    async def invalidate_active_otps(self, email: str) -> None:
        """Mark any existing active OTP challenges for email as used/invalidated."""
        await self.password_resets.update_many(
            {
                "email": email.strip().lower(),
                "purpose": "email_otp",
                "used": False,
            },
            {"$set": {"used": True}},
        )

    async def increment_otp_attempts(self, reset_id: str) -> int:
        """Atomically increment failed OTP attempt counter and return new count."""
        if not ObjectId.is_valid(reset_id):
            return 3
        updated = await self.password_resets.find_one_and_update(
            {"_id": ObjectId(reset_id)},
            {"$inc": {"attempts": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            return 3
        count = updated.get("attempts", 0)
        max_attempts = updated.get("max_attempts", 3)
        if count >= max_attempts:
            await self.password_resets.update_one(
                {"_id": ObjectId(reset_id)},
                {"$set": {"used": True}},
            )
        return count

    async def consume_otp_atomically(self, reset_id: str) -> bool:
        """Atomically mark OTP as used. Returns True if consumed, False if already used."""
        if not ObjectId.is_valid(reset_id):
            return False
        result = await self.password_resets.find_one_and_update(
            {"_id": ObjectId(reset_id), "used": False},
            {"$set": {"used": True}},
            return_document=ReturnDocument.AFTER,
        )
        return result is not None

    async def consume_reset_session_atomically(self, token_hash: str) -> PasswordResetInDB | None:
        """Atomically validate, verify unexpired, and consume a password reset session token."""
        now = datetime.now(UTC)
        doc = await self.password_resets.find_one_and_update(
            {
                "token_hash": token_hash,
                "purpose": "password_reset_session",
                "used": False,
                "expires_at": {"$gt": now},
            },
            {"$set": {"used": True}},
            return_document=ReturnDocument.AFTER,
        )
        return self._doc_to_password_reset(doc) if doc else None

    async def mark_password_reset_used(self, reset_id: str) -> None:
        """Mark a password reset token as redeemed."""
        if ObjectId.is_valid(reset_id):
            await self.password_resets.update_one(
                {"_id": ObjectId(reset_id)},
                {"$set": {"used": True}},
            )
