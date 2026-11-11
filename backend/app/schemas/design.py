from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DesignWallSchema(BaseModel):
    """Wall dimension and appearance specifications."""

    width_inches: float = Field(
        default=120.0,
        ge=24.0,
        le=480.0,
        description="Total wall width in inches",
    )
    height_inches: float = Field(
        default=96.0,
        ge=24.0,
        le=240.0,
        description="Total wall height in inches",
    )
    color_hex: str = Field(
        default="#F0EBE4",
        pattern=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
        description="Wall paint color swatch hex code",
    )
    texture: str = Field(
        default="plaster_smooth",
        max_length=50,
        description="Wall surface finish / texture",
    )
    display_unit: Literal["in", "cm", "mm", "ft"] = Field(
        default="in",
        description="Measurement unit for dimensions",
    )
    has_sofa: bool = Field(
        default=False,
        description="Whether a couch/sofa clearance is positioned on the wall",
    )

    model_config = ConfigDict(from_attributes=True)


class CreateDesignRequest(BaseModel):
    """Payload for creating a new design project (EP-DSGN-01)."""

    title: str = Field(
        min_length=1,
        max_length=100,
        description="Descriptive title for the gallery wall design",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional customer design notes or description",
    )
    wall: DesignWallSchema = Field(
        default_factory=DesignWallSchema,
        description="Wall specifications",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Title cannot be empty or blank")
        return trimmed


class UpdateDesignRequest(BaseModel):
    """Payload for updating an existing design's metadata (EP-DSGN-05)."""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Updated gallery wall title",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Updated design notes or description",
    )
    status: Literal["draft", "saved", "ordered"] | None = Field(
        default=None,
        description="Updated project workflow status",
    )
    wall: DesignWallSchema | None = Field(
        default=None,
        description="Updated wall dimensions or color swatch",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Title cannot be empty or blank")
            return trimmed
        return v


class MattingInputSchema(BaseModel):
    """Matboard border specification for a frame."""

    enabled: bool = Field(default=True, description="Whether matboard border is active")
    top_inches: float = Field(default=2.0, ge=0.0, le=12.0)
    bottom_inches: float = Field(default=2.0, ge=0.0, le=12.0)
    left_inches: float = Field(default=2.0, ge=0.0, le=12.0)
    right_inches: float = Field(default=2.0, ge=0.0, le=12.0)
    color_hex: str = Field(
        default="#F4F3F3",
        pattern=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
        description="Mount color swatch hex code",
    )

    model_config = ConfigDict(from_attributes=True)


class DesignItemInputSchema(BaseModel):
    """Input specification for an individual placed frame in a version (EP-DSGN-02)."""

    item_id: str = Field(min_length=1, max_length=50, description="Client frame identifier")
    frame_id: str = Field(
        min_length=1, max_length=50, description="Moulding ID or size template identifier"
    )
    photo_id: str | None = Field(
        default=None,
        description="MongoDB ObjectId hex string of user-uploaded photo",
    )
    sample_id: str | None = Field(
        default=None,
        max_length=50,
        description="Stock sample photograph ID if using demo assets",
    )
    position_x_inches: float = Field(
        ge=0.0, le=480.0, description="X coordinate of top-left corner"
    )
    position_y_inches: float = Field(
        ge=0.0, le=240.0, description="Y coordinate of top-left corner"
    )
    photo_width_inches: float = Field(gt=0.0, le=120.0, description="Photo inner opening width")
    photo_height_inches: float = Field(gt=0.0, le=120.0, description="Photo inner opening height")
    total_width_inches: float | None = Field(
        default=None,
        gt=0.0,
        le=120.0,
        description="Total outer frame width (auto-calculated if omitted)",
    )
    total_height_inches: float | None = Field(
        default=None,
        gt=0.0,
        le=120.0,
        description="Total outer frame height (auto-calculated if omitted)",
    )
    orientation: Literal["portrait", "landscape", "square"] = Field(
        default="portrait",
        description="Frame orientation",
    )
    finish_id: str | None = Field(default=None, max_length=50, description="Moulding finish ID")
    size_id: str | None = Field(
        default=None, max_length=50, description="Frame size standard identifier"
    )
    matting: MattingInputSchema = Field(default_factory=MattingInputSchema)
    glass_type: str = Field(default="standard", max_length=50, description="Glazing type")


class SaveDesignVersionRequest(BaseModel):
    """Payload for creating an immutable design version snapshot (EP-DSGN-02)."""

    layout_type: str = Field(
        default="custom",
        max_length=50,
        description="Layout classification (custom, grid, salon, centre, row, triptych)",
    )
    template_id: str | None = Field(
        default=None,
        max_length=100,
        description="Preset layout template identifier if based on a template",
    )
    items: list[DesignItemInputSchema] = Field(
        min_length=1,
        max_length=32,
        description="Array of 1 to 32 placed frames",
    )
    layout_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional layout solver parameters: style, gap_inches, seed, variant",
    )
    preview: dict[str, Any] | None = Field(
        default=None,
        description="Optional preview flags: sofa, index_badges, guides",
    )


class BoundingBoxSchema(BaseModel):
    """2D Axis-Aligned Bounding Box dimensions in inches."""

    x: float
    y: float
    width: float
    height: float

    model_config = ConfigDict(from_attributes=True)


class DesignItemOutput(BaseModel):
    """Output representation of a placed frame within a layout version."""

    item_id: str
    frame_id: str
    photo_id: str | None = None
    photo_missing: bool = Field(
        default=False,
        description="True if referenced photo is missing, deleted, or inaccessible",
    )
    sample_id: str | None = None
    position_x_inches: float
    position_y_inches: float
    photo_width_inches: float
    photo_height_inches: float
    total_width_inches: float
    total_height_inches: float
    orientation: str
    finish_id: str | None = None
    size_id: str | None = None
    matting: MattingInputSchema
    glass_type: str

    model_config = ConfigDict(from_attributes=True)


class DesignVersionOutput(BaseModel):
    """Full detail of a layout version including all frame items."""

    id: str
    design_id: str
    version_number: int
    layout_type: str
    template_id: str | None = None
    items_count: int
    bounding_box: BoundingBoxSchema
    items: list[DesignItemOutput] = Field(default_factory=list)
    layout_metadata: dict[str, Any] | None = None
    preview: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DesignVersionSummaryResponse(BaseModel):
    """Compact summary response after saving a design version (EP-DSGN-02)."""

    version_id: str
    design_id: str
    version_number: int
    layout_type: str
    items_count: int
    bounding_box: BoundingBoxSchema
    created_at: datetime


class DesignOut(BaseModel):
    """Standard representation of a design project."""

    id: str
    user_id: str
    title: str
    description: str | None = None
    wall: DesignWallSchema
    current_version_id: str | None = None
    current_version_number: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DesignDetailOut(BaseModel):
    """Comprehensive design document response for loading a canvas (EP-DSGN-03)."""

    id: str
    user_id: str
    title: str
    description: str | None = None
    status: str
    wall: DesignWallSchema
    current_version_id: str | None = None
    current_version: DesignVersionOutput | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DesignListItemOut(BaseModel):
    """Item summary for user design card listings (EP-DSGN-04)."""

    id: str
    user_id: str
    title: str
    description: str | None = None
    status: str
    wall: DesignWallSchema
    current_version_id: str | None = None
    current_version_number: int | None = None
    items_count: int = Field(default=0, description="Number of frames in the current version")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DesignListResponse(BaseModel):
    """Paginated list of saved designs (EP-DSGN-04)."""

    items: list[DesignListItemOut]
    total: int
    page: int
    page_size: int
    total_pages: int
