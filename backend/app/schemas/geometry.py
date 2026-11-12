"""Pydantic schemas for Phase 5 Geometry & Intelligent Wall Layout Engine.

Covers EP-GEO-01 (validate-layout), EP-GEO-02 (generate-layout),
regenerate-layout, and redesign-layout endpoints.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.modules import catalog
from app.modules.catalog import RULES, FinishId, FrameSizeId


class WallInput(BaseModel):
    """Wall specifications in inches."""

    width_inches: float = Field(
        ge=RULES.wall_width_min_inches,
        le=RULES.wall_width_max_inches,
        description="Total wall width in inches (36–480)",
    )
    height_inches: float = Field(
        ge=RULES.wall_height_min_inches,
        le=RULES.wall_height_max_inches,
        description="Total wall height in inches (48–240)",
    )
    margin_inches: float = Field(
        default=RULES.wall_margin_inches,
        ge=0.0,
        le=36.0,
        description="Minimum clear safety border from edges of the wall",
    )
    has_sofa: bool = Field(
        default=False,
        description="Whether a standard sofa/couch clearance is present along the bottom",
    )
    eye_level_height_inches: float = Field(
        default=RULES.eye_level_inches,
        ge=36.0,
        le=72.0,
        description="Standard human eye-level height measured from the floor",
    )


class MattingInput(BaseModel):
    """Matboard border margins in inches."""

    enabled: bool = Field(default=True, description="Whether matboard border is active")
    top_inches: float = Field(default=2.0, ge=0.0, le=RULES.mat_max_inches)
    bottom_inches: float = Field(default=2.0, ge=0.0, le=RULES.mat_max_inches)
    left_inches: float = Field(default=2.0, ge=0.0, le=RULES.mat_max_inches)
    right_inches: float = Field(default=2.0, ge=0.0, le=RULES.mat_max_inches)


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
    size_id: FrameSizeId | None = Field(
        default=None,
        description="Catalog frame size; sets the photo opening from size + orientation",
    )
    finish_id: FinishId | None = Field(
        default=None,
        description="Catalog finish; sets frame_profile_width_inches from the finish",
    )

    @model_validator(mode="after")
    def _apply_catalog(self) -> "FrameItemInput":
        size = catalog.get_frame_size(self.size_id)
        if size:
            w, h = size.oriented(self.orientation)
            explicit = {"photo_width_inches", "photo_height_inches"} & self.model_fields_set
            if explicit and (
                abs(self.photo_width_inches - w) > 0.01 or abs(self.photo_height_inches - h) > 0.01
            ):
                raise ValueError("photo_width/height_inches don't match size_id and orientation")
            self.photo_width_inches, self.photo_height_inches = w, h
        finish = catalog.get_finish(self.finish_id)
        if finish:
            if (
                "frame_profile_width_inches" in self.model_fields_set
                and abs(self.frame_profile_width_inches - finish.profile_inches) > 0.001
            ):
                raise ValueError("frame_profile_width_inches doesn't match finish_id")
            self.frame_profile_width_inches = finish.profile_inches
        return self


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
        max_length=RULES.frame_count_max,
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
        max_length=RULES.frame_count_max,
        description="Picture frames or photographs to arrange (1–16)",
    )
    layout_style: Literal["grid", "salon", "centre", "row"] | None = Field(
        default=None,
        description="Optional preferred layout style. If omitted, engine determines best fit.",
    )
    spacing_inches: float = Field(
        default=3.0,
        ge=RULES.gap_min_inches,
        le=RULES.gap_max_inches,
        description="Distance between frames in inches (0–12)",
    )
    engine_mode: Literal["smart_llm", "geometric"] = Field(
        default="geometric",
        description="Mode: 'smart_llm' (Groq curator) or 'geometric'.",
    )
    seed: int | None = Field(
        default=None,
        description="Optional deterministic RNG seed. If omitted, fresh seed is generated.",
    )
    variant: int = Field(
        default=0, ge=0, lt=RULES.variant_count, description="Alternative variation index (0–2)"
    )


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
    frames: list[FrameItemInput] = Field(min_length=1, max_length=RULES.frame_count_max)
    layout_style: Literal["grid", "salon", "centre", "row"]
    current_seed: int
    current_variant: int = 0
    spacing_inches: float = Field(default=3.0, ge=RULES.gap_min_inches, le=RULES.gap_max_inches)


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
    frames: list[FrameItemInput] = Field(min_length=1, max_length=RULES.frame_count_max)
    current_layout_style: Literal["grid", "salon", "centre", "row"]
    spacing_inches: float = Field(default=3.0, ge=RULES.gap_min_inches, le=RULES.gap_max_inches)
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
