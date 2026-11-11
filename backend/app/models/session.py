from datetime import UTC, datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.user import PyObjectId


class RefreshTokenInDB(BaseModel):
    """Internal MongoDB refresh token session document representation."""

    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: PyObjectId
    token_hash: str
    family_id: str
    is_revoked: bool = Field(default=False)
    replaced_by: PyObjectId | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )


class PasswordResetInDB(BaseModel):
    """Internal MongoDB password reset & OTP challenge document representation."""

    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: PyObjectId
    email: str | None = None
    token_hash: str
    purpose: str = Field(default="password_reset")
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=3)
    resend_available_at: datetime | None = None
    expires_at: datetime
    used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )
