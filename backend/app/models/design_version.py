from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, Field


class MattingInDB(BaseModel):
    """Matboard border specification stored in database."""

    enabled: bool = Field(default=True, description="Whether matboard border is active")
    top_inches: float = Field(default=2.0, ge=0.0)
    bottom_inches: float = Field(default=2.0, ge=0.0)
    left_inches: float = Field(default=2.0, ge=0.0)
    right_inches: float = Field(default=2.0, ge=0.0)
    color_hex: str = Field(default="#F4F3F3", description="Mount color hex swatch")


class DesignItemInDB(BaseModel):
    """Specification of an individual frame placed in a layout version."""

    item_id: str = Field(description="Client-side identifier for this frame")
    frame_id: str = Field(description="Moulding ID or size template identifier")
    photo_id: str | None = Field(default=None, description="MongoDB ObjectId of user photo asset")
    sample_id: str | None = Field(default=None, description="Stock sample photo identifier")
    position_x_inches: float = Field(
        ge=0.0, description="X coordinate of top-left corner in inches"
    )
    position_y_inches: float = Field(
        ge=0.0, description="Y coordinate of top-left corner in inches"
    )
    photo_width_inches: float = Field(gt=0.0, description="Photo inner opening width in inches")
    photo_height_inches: float = Field(gt=0.0, description="Photo inner opening height in inches")
    total_width_inches: float = Field(gt=0.0, description="Total outer frame width in inches")
    total_height_inches: float = Field(gt=0.0, description="Total outer frame height in inches")
    orientation: str = Field(
        default="portrait", description="Orientation: portrait, landscape, square"
    )
    finish_id: str | None = Field(default=None, description="Moulding finish ID")
    size_id: str | None = Field(default=None, description="Frame size standard identifier")
    matting: MattingInDB = Field(default_factory=MattingInDB)
    glass_type: str = Field(
        default="standard", description="Glazing type: standard, museum_uv, etc."
    )


class BoundingBoxInDB(BaseModel):
    """2D Axis-Aligned Bounding Box in inches."""

    x: float
    y: float
    width: float
    height: float


class DesignVersionInDB(BaseModel):
    """Immutable snapshot of a layout version in 'design_versions' collection."""

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    design_id: str = Field(description="Parent designs ObjectId hex string")
    version_number: int = Field(description="Monotonic sequential version number (1, 2, ...)")
    layout_type: str = Field(
        default="custom", description="Layout style: custom, grid, salon, etc."
    )
    template_id: str | None = Field(
        default=None, description="Preset template identifier if based on a template"
    )
    items: list[DesignItemInDB] = Field(
        default_factory=list, description="Array of frame items in this version"
    )
    bounding_box: BoundingBoxInDB = Field(description="Calculated outer envelope of all frames")
    layout_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Layout generation parameters: style, gap_inches, seed, variant",
    )
    preview: dict[str, Any] | None = Field(
        default=None,
        description="Display preview flags: sofa, index_badges, guides",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "_id": "672d0222e4b0123456789bb2",
                "design_id": "672d0111e4b0123456789aa1",
                "version_number": 1,
                "layout_type": "grid",
                "template_id": None,
                "items": [],
                "bounding_box": {"x": 24.0, "y": 20.0, "width": 18.0, "height": 22.0},
            }
        },
    }
