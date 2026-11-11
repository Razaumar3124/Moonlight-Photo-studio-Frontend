from datetime import UTC, datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.user import PyObjectId


class TemplateSlotInDB(BaseModel):
    """Slot geometry relative to arrangement wall and photo aspect ratio."""

    slot_id: str
    relative_x_ratio: float
    relative_y_ratio: float
    default_photo_width_inches: float
    default_photo_height_inches: float
    aspect_ratio: float

    model_config = ConfigDict(extra="forbid")


class LayoutTemplateInDB(BaseModel):
    """Internal MongoDB document model for layout_templates collection."""

    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    slug: str
    name: str
    description: str
    category: str
    min_wall_width_inches: float
    min_wall_height_inches: float
    recommended_wall_width_inches: float
    recommended_wall_height_inches: float
    slots_count: int
    slots: list[TemplateSlotInDB] = Field(default_factory=list)
    thumbnail_url: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )
