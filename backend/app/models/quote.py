"""MongoDB document representations for quotation requests and digital reports."""

from datetime import UTC, datetime
from typing import Annotated, Any

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def validate_object_id(v: Any) -> str:
    """Validate or convert BSON ObjectId into 24-character hexadecimal string."""
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str) and ObjectId.is_valid(v):
        return v
    raise ValueError("Invalid ObjectId string")


PyObjectId = Annotated[str, BeforeValidator(validate_object_id)]


class QuoteContactSnapshot(BaseModel):
    """Customer profile contact details captured from the authenticated user record."""

    full_name: str = Field(description="Customer full name from profile")
    email: str = Field(description="Customer primary email address")
    phone: str | None = Field(default=None, description="Customer registered mobile number")


class QuoteWallSnapshot(BaseModel):
    """Immutable snapshot of the wall dimensions and backdrop configuration."""

    width_inches: float = Field(gt=0.0, description="Authoritative wall width in inches")
    height_inches: float = Field(gt=0.0, description="Authoritative wall height in inches")
    color_hex: str = Field(default="#F0EBE4", description="Wall backdrop paint swatch hex")
    texture: str | None = Field(default=None, description="Wall texture surface style")
    display_unit: str = Field(default="in", description="Customer's preferred measurement unit")
    has_sofa: bool = Field(default=False, description="Whether sofa clearance was visible")


class QuoteFrameSnapshot(BaseModel):
    """Specification of an individual frame item in the quote snapshot."""

    item_id: str = Field(description="Client-side identifier for this frame")
    frame_number: int = Field(ge=1, description="Sequential 1-based frame label in layout")
    size_id: str = Field(description="Standard frame opening dimension key")
    orientation: str = Field(
        default="portrait", description="Orientation: portrait, landscape, square"
    )
    finish_id: str = Field(description="Moulding finish key")
    finish_name: str | None = Field(default=None, description="Human-readable finish name")
    width_inches: float = Field(gt=0.0, description="Outer frame width in inches")
    height_inches: float = Field(gt=0.0, description="Outer frame height in inches")
    position_x_inches: float = Field(
        default=0.0, ge=0.0, description="X coordinate of top-left corner in inches"
    )
    position_y_inches: float = Field(
        default=0.0, ge=0.0, description="Y coordinate of top-left corner in inches"
    )
    mount_enabled: bool = Field(default=True, description="Whether matboard border is active")
    mount_color_name: str | None = Field(
        default=None, description="Mount / matboard color description"
    )
    mount_margin_inches: float = Field(
        default=0.0, ge=0.0, description="Matboard border margin in inches"
    )
    photo_kind: str | None = Field(
        default=None, description="Photo source kind: upload, sample, or none"
    )
    photo_id: str | None = Field(default=None, description="User photo ObjectId string if uploaded")
    sample_id: str | None = Field(default=None, description="Sample photo ID if stock asset")
    photo_name: str | None = Field(default=None, description="Display name of assigned photo")


class QuoteInDB(BaseModel):
    """MongoDB document representation for 'quotes' collection."""

    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    quote_reference: str = Field(
        description="Unique sequential quote identifier (e.g., SQ-2026-0012)"
    )
    user_id: str = Field(description="Owner user ObjectId hex string")
    customer: QuoteContactSnapshot = Field(description="Customer contact details snapshot")
    design_id: str | None = Field(default=None, description="Associated design ObjectId if saved")
    design_title: str = Field(
        default="Memory Wall Design", description="Customer's title for this design"
    )
    layout_style: str = Field(
        default="grid", description="Arrangement style: grid, salon, centre, row, custom"
    )
    wall: QuoteWallSnapshot = Field(description="Wall dimension and backdrop snapshot")
    frames: list[QuoteFrameSnapshot] = Field(
        default_factory=list, description="Array of frame specifications"
    )
    preview_image_key: str = Field(
        description="Cloudflare R2 storage key for high-res wall preview export"
    )
    preview_image_content_type: str = Field(
        default="image/png", description="MIME content type of stored preview"
    )
    share_token_hash: str = Field(
        description="SHA-256 hash of the unguessable shareable report token"
    )
    share_token_prefix: str = Field(
        description="First 8 characters of share token for lookup logging"
    )
    status: str = Field(
        default="draft",
        description="Quote status: draft, pending_review, contacted, converted, expired",
    )
    expires_at: datetime = Field(description="UTC timestamp after which share link is invalid")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("expires_at", "created_at", "updated_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        """Ensure datetimes deserialized from MongoDB without tzinfo are timezone-aware UTC."""
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )
