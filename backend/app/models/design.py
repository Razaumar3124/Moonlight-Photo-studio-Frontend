from datetime import UTC, datetime

from bson import ObjectId
from pydantic import BaseModel, Field


class DesignWallInDB(BaseModel):
    """Persisted wall dimensions and styling for a design."""

    width_inches: float = Field(default=120.0, description="Wall width in inches")
    height_inches: float = Field(default=96.0, description="Wall height in inches")
    color_hex: str = Field(default="#F0EBE4", description="Wall paint color swatch")
    texture: str = Field(default="plaster_smooth", description="Wall surface texture")
    display_unit: str = Field(default="in", description="Measurement unit (in, cm, mm, ft)")
    has_sofa: bool = Field(default=False, description="Whether sofa clearance is enabled")


class DesignInDB(BaseModel):
    """MongoDB document representation for 'designs' collection."""

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str = Field(description="Owner user ObjectId hex string")
    title: str = Field(description="Human-readable title for the gallery wall design")
    description: str | None = Field(
        default=None, description="Optional design notes or description"
    )
    wall: DesignWallInDB = Field(default_factory=DesignWallInDB)
    current_version_id: str | None = Field(
        default=None, description="ObjectId of latest design_versions"
    )
    current_version_number: int | None = Field(
        default=None, description="Latest sequential version number"
    )
    status: str = Field(default="draft", description="Design status: draft, saved, or ordered")
    version_counter: int = Field(
        default=0, description="Atomic monotonic sequence counter for versions"
    )
    is_deleted: bool = Field(default=False, description="Soft deletion flag")
    deleted_at: datetime | None = Field(default=None, description="UTC timestamp of soft deletion")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "_id": "672d0111e4b0123456789aa1",
                "user_id": "672cf1a9e4b0123456789abc",
                "title": "Living Room Gallery Wall",
                "description": "Custom layout for dining wall",
                "status": "draft",
                "wall": {
                    "width_inches": 120.0,
                    "height_inches": 96.0,
                    "color_hex": "#F0EBE4",
                    "texture": "plaster_smooth",
                    "display_unit": "in",
                    "has_sofa": False,
                },
                "current_version_id": None,
                "current_version_number": None,
                "version_counter": 0,
                "is_deleted": False,
            }
        },
    }
