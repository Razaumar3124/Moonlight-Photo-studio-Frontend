"""Pydantic schemas for Phase 5 Geometry & Intelligent Wall Layout Engine.

Covers EP-GEO-01 (validate-layout), EP-GEO-02 (generate-layout),
regenerate-layout, and redesign-layout endpoints.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class WallInput(BaseModel):
    """Wall specifications in inches."""

    width_inches: float = Field(ge=24.0, le=480.0, description="Total wall width in inches")
    height_inches: float = Field(ge=24.0, le=240.0, description="Total wall height in inches")
    margin_inches: float = Field(
        default=6.0,
        ge=0.0,
        le=36.0,
        description="Minimum clear safety border from edges of the wall",
    )
    has_sofa: bool = Field(
        default=False,
        description="Whether a standard sofa/couch clearance is present along the bottom",
    )
    eye_level_height_inches: float = Field(
        default=57.0,
        ge=36.0,
        le=72.0,
        description="Standard human eye-level height measured from the floor",
    )


class MattingInput(BaseModel):
    """Matboard border margins in inches."""

    enabled: bool = Field(default=True, description="Whether matboard border is active")
    top_inches: float = Field(default=2.0, ge=0.0, le=8.0)
    bottom_inches: float = Field(default=2.0, ge=0.0, le=8.0)
    left_inches: float = Field(default=2.0, ge=0.0, le=8.0)
    right_inches: float = Field(default=2.0, ge=0.0, le=8.0)


class FrameItemInput(BaseModel):
    """Specification of an individual picture frame to be placed on the wall."""

    item_id: str = Field(description="Unique client-side identifier for this frame")
    photo_id: str | None = Field(
        default=None,
        description="Optional MongoDB ObjectId referencing an uploaded photograph",
    )
    photo_width_inches: float = Field(
        default=12.0,
        gt=0.0,
        le=60.0,
        description="Photo opening width in inches",
    )
    photo_height_inches: float = Field(
        default=16.0,
        gt=0.0,
        le=60.0,
        description="Photo opening height in inches",
    )
    matting: MattingInput = Field(default_factory=MattingInput)
    frame_profile_width_inches: float = Field(
        default=1.0,
        ge=0.25,
        le=4.0,
        description="Moulding face profile width in inches",
    )
    orientation: Literal["portrait", "landscape", "square"] = Field(
        default="portrait",
        description="Target frame orientation",
    )


class BoundingBox(BaseModel):
    """2D Axis-Aligned Bounding Box."""

    x: float
    y: float
    width: float
    height: float


class PlacedItemOutput(BaseModel):
    """Calculated absolute position and dimensions of an arranged frame."""

    item_id: str
    photo_id: str | None = None
    outer_x_inches: float
    outer_y_inches: float
    outer_width_inches: float
    outer_height_inches: float
    photo_x_inches: float
    photo_y_inches: float
    photo_width_inches: float
    photo_height_inches: float


class GeometryValidationErrorItem(BaseModel):
    code: str
    message: str
    item_ids: list[str] = Field(default_factory=list)


class GeometryValidationWarningItem(BaseModel):
    code: str
    message: str


# ==============================================================================
# Endpoint 1: Validate Layout (EP-GEO-01)
# ==============================================================================


class PlacedFrameValidateInput(BaseModel):
    item_id: str
    outer_x_inches: float
    outer_y_inches: float
    outer_width_inches: float
    outer_height_inches: float


class ValidateLayoutRequest(BaseModel):
    wall: WallInput
    frames: list[PlacedFrameValidateInput] = Field(
        min_length=1,
        description="Array of user-positioned frame outer bounding boxes",
    )


class ValidateLayoutResponse(BaseModel):
    is_valid: bool
    bounding_box: BoundingBox
    wall_coverage_percentage: float
    errors: list[GeometryValidationErrorItem] = Field(default_factory=list)
    warnings: list[GeometryValidationWarningItem] = Field(default_factory=list)
    calculated_items: list[dict[str, Any]] = Field(default_factory=list)


# ==============================================================================
# Endpoint 2: Generate Layout (EP-GEO-02)
# ==============================================================================


class GenerateLayoutRequest(BaseModel):
    wall: WallInput
    frames: list[FrameItemInput] = Field(
        min_length=1,
        max_length=24,
        description="Picture frames or photographs to arrange",
    )
    layout_style: Literal["grid", "salon", "centre", "row"] | None = Field(
        default=None,
        description="Optional preferred layout style. If omitted, engine determines best fit.",
    )
    spacing_inches: float = Field(
        default=3.0,
        ge=0.5,
        le=12.0,
        description="Distance between frames in inches",
    )
    engine_mode: Literal["smart_llm", "geometric"] = Field(
        default="geometric",
        description="Mode: 'smart_llm' (Groq curator) or 'geometric'.",
    )
    seed: int | None = Field(
        default=None,
        description="Optional deterministic RNG seed. If omitted, fresh seed is generated.",
    )
    variant: int = Field(default=0, ge=0, description="Alternative variation index")


class GenerateLayoutResponse(BaseModel):
    layout_type: Literal["grid", "salon", "centre", "row"]
    variant: int
    seed: int
    bounding_box: BoundingBox
    wall_coverage_percentage: float
    fits: bool
    engine_used: Literal["smart_llm", "geometric", "fallback_geometric"]
    ai_rationale: str | None = None
    warnings: list[GeometryValidationWarningItem] = Field(default_factory=list)
    items: list[PlacedItemOutput]


# ==============================================================================
# Endpoint 3: Regenerate Layout
# ==============================================================================


class RegenerateLayoutRequest(BaseModel):
    wall: WallInput
    frames: list[FrameItemInput] = Field(min_length=1, max_length=24)
    layout_style: Literal["grid", "salon", "centre", "row"]
    current_seed: int
    current_variant: int = 0
    spacing_inches: float = Field(default=3.0, ge=0.5, le=12.0)


class RegenerateLayoutResponse(BaseModel):
    layout_type: Literal["grid", "salon", "centre", "row"]
    variant: int
    seed: int
    bounding_box: BoundingBox
    wall_coverage_percentage: float
    fits: bool
    engine_used: Literal["geometric"] = "geometric"
    items: list[PlacedItemOutput]


# ==============================================================================
# Endpoint 4: Redesign Layout
# ==============================================================================


class RedesignLayoutRequest(BaseModel):
    wall: WallInput
    frames: list[FrameItemInput] = Field(min_length=1, max_length=24)
    current_layout_style: Literal["grid", "salon", "centre", "row"]
    spacing_inches: float = Field(default=3.0, ge=0.5, le=12.0)
    engine_mode: Literal["smart_llm", "geometric"] = Field(default="geometric")


class RedesignLayoutResponse(BaseModel):
    layout_type: Literal["grid", "salon", "centre", "row"]
    variant: int
    seed: int
    bounding_box: BoundingBox
    wall_coverage_percentage: float
    fits: bool
    engine_used: Literal["smart_llm", "geometric", "fallback_geometric"]
    ai_rationale: str | None = None
    items: list[PlacedItemOutput]
