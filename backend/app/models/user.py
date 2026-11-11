from datetime import UTC, datetime
from typing import Annotated, Any

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def validate_object_id(v: Any) -> str:
    """Validate or convert BSON ObjectId into 24-character hexadecimal string."""
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str) and ObjectId.is_valid(v):
        return v
    raise ValueError("Invalid ObjectId string")


PyObjectId = Annotated[str, BeforeValidator(validate_object_id)]


class UserInDB(BaseModel):
    """Internal MongoDB user document representation."""

    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    email: str
    phone: str | None = None
    password_hash: str | None = None
    full_name: str
    role: str = Field(default="customer")
    is_active: bool = Field(default=True)
    auth_provider: str = Field(default="local")
    google_id: str | None = None
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )
