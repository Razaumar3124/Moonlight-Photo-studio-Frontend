from datetime import UTC, datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    """Embedded frame finish colour option with hex code and face profile width.

    `id` is the planner finish ID (app/modules/catalog.py) for wood finishes. Documents seeded
    before it existed get one derived from the name ("Natural Oak" → "natural-oak").
    """

    id: str
    name: str
    hex: str
    profile_in: float

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _derive_legacy_id(cls, data: object) -> object:
        if isinstance(data, dict) and not data.get("id") and isinstance(data.get("name"), str):
            data = {**data, "id": "-".join(data["name"].lower().split())}
        return data


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
