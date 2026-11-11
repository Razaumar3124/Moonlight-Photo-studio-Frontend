from datetime import UTC, datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.user import PyObjectId

FrameMaterialCategory = Literal["wood", "metal", "synthetic"]


class FrameMaterialInDB(BaseModel):
    """Internal MongoDB document model for frame_materials collection."""

    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    code: str
    name: str
    category: FrameMaterialCategory
    finish: str
    base_price_per_linear_inch: str
    waste_factor_percentage: float
    thumbnail_url: str
    is_available: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )


class FrameColorOption(BaseModel):
    """Embedded frame finish colour option with hex code and face profile width."""

    name: str
    hex: str
    profile_in: float

    model_config = ConfigDict(extra="forbid")


class FrameMoldingInDB(BaseModel):
    """Internal MongoDB document model for frame_moldings collection."""

    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    sku: str
    name: str
    material_id: PyObjectId
    material_name: str
    profile_width_inches: float
    profile_depth_inches: float
    rabbet_depth_inches: float
    price_per_linear_inch: str
    available_colors: list[FrameColorOption] = Field(default_factory=list)
    thumbnail_url: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )
