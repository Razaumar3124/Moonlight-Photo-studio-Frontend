from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules import catalog
from app.modules.catalog import (
    RULES,
    DisplayUnit,
    FinishId,
    FrameSizeId,
    LayoutStyleId,
    LayoutTypeId,
    MountColourId,
    PaintShadeId,
)

HexColor = Annotated[str, Field(pattern=r"^#(?:[0-9a-fA-F]{3}){1,2}$")]
ObjectIdStr = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{24}$")]


class DesignWallSchema(BaseModel):
    """Wall dimensions and appearance (input). Limits match the planner (GET /catalog rules)."""

    width_inches: float = Field(
        default=120.0,
        ge=RULES.wall_width_min_inches,
        le=RULES.wall_width_max_inches,
        description="Total wall width in inches (36–480)",
    )
    height_inches: float = Field(
        default=96.0,
        ge=RULES.wall_height_min_inches,
        le=RULES.wall_height_max_inches,
        description="Total wall height in inches (48–240)",
    )
    paint_id: PaintShadeId | None = Field(
        default=None,
        description="Catalog paint shade; when given, color_hex is set from the catalog",
    )
    color_hex: HexColor = Field(default="#F0EBE4", description="Wall paint color hex code")
    texture: str = Field(
        default="plaster_smooth",
        max_length=50,
        description="Wall surface finish / texture",
    )
    display_unit: DisplayUnit = Field(
        default="in",
        description="Unit the customer sees (ft, in, cm, m; mm kept for older clients). "
        "All API values stay in inches.",
    )
    has_sofa: bool = Field(
        default=False,
        description="Whether the reference sofa (and its clearance) is shown",
    )

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _paint_colour(self) -> "DesignWallSchema":
        shade = catalog.get_paint_shade(self.paint_id)
        if shade:
            self.color_hex = shade.hex
        return self


class DesignWallOut(BaseModel):
    """Stored wall (output). Not range-checked, so designs saved under older rules still load."""

    width_inches: float
    height_inches: float
    paint_id: str | None = None
    color_hex: str
    texture: str
    display_unit: str
    has_sofa: bool

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
    """Mount (matboard) border per side, 0–6 in, and its colour."""

    enabled: bool = Field(default=True, description="Whether the mount is shown")
    top_inches: float = Field(default=2.0, ge=0.0, le=RULES.mat_max_inches)
    bottom_inches: float = Field(default=2.0, ge=0.0, le=RULES.mat_max_inches)
    left_inches: float = Field(default=2.0, ge=0.0, le=RULES.mat_max_inches)
    right_inches: float = Field(default=2.0, ge=0.0, le=RULES.mat_max_inches)
    color_id: MountColourId | None = Field(
        default=None,
        description="Catalog mount colour; when given, color_hex is set from the catalog",
    )
    color_hex: HexColor = Field(default="#F4F3F3", description="Mount color hex code")

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _mount_colour(self) -> "MattingInputSchema":
        colour = catalog.get_mount_colour(self.color_id)
        if colour:
            self.color_hex = colour.hex
        return self


class MattingOut(BaseModel):
    """Stored mount (output, not range-checked)."""

    enabled: bool
    top_inches: float
    bottom_inches: float
    left_inches: float
    right_inches: float
    color_id: str | None = None
    color_hex: str

    model_config = ConfigDict(from_attributes=True)


class DesignItemInputSchema(BaseModel):
    """A placed frame in a version (EP-DSGN-02).

    With `size_id` the photo opening must equal the catalog size in the given orientation.
    With `finish_id` the outer size is computed on the server (opening + mats + moulding face).
    """

    item_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Client frame identifier, unique within the version",
    )
    frame_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Moulding or product reference; defaults to size_id (or 'custom')",
    )
    photo_id: ObjectIdStr | None = Field(
        default=None,
        description="ID of a photo uploaded by the same user",
    )
    sample_id: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9][a-z0-9-]{0,49}$",
        description="Bundled sample photo ID (e.g. frame-01)",
    )
    position_x_inches: float = Field(
        ge=0.0, le=RULES.wall_width_max_inches, description="X of the outer top-left corner"
    )
    position_y_inches: float = Field(
        ge=0.0, le=RULES.wall_height_max_inches, description="Y of the outer top-left corner"
    )
    photo_width_inches: float = Field(gt=0.0, le=120.0, description="Photo opening width")
    photo_height_inches: float = Field(gt=0.0, le=120.0, description="Photo opening height")
    total_width_inches: float | None = Field(
        default=None,
        gt=0.0,
        le=RULES.wall_width_max_inches,
        description="Outer frame width; computed by the server when finish_id is given",
    )
    total_height_inches: float | None = Field(
        default=None,
        gt=0.0,
        le=RULES.wall_height_max_inches,
        description="Outer frame height; computed by the server when finish_id is given",
    )
    orientation: Literal["portrait", "landscape", "square"] = Field(
        default="portrait",
        description="Frame orientation",
    )
    finish_id: FinishId | None = Field(default=None, description="Catalog wood finish")
    size_id: FrameSizeId | None = Field(default=None, description="Catalog frame size")
    matting: MattingInputSchema = Field(default_factory=MattingInputSchema)
    glass_type: str = Field(
        default="standard", max_length=50, pattern=r"^[a-z0-9_]+$", description="Glazing type"
    )

    @model_validator(mode="after")
    def _check_references(self) -> "DesignItemInputSchema":
        if self.photo_id and self.sample_id:
            raise ValueError("Use either photo_id or sample_id, not both")
        size = catalog.get_frame_size(self.size_id)
        if size:
            if self.orientation == "square":
                raise ValueError("Catalog sizes are portrait or landscape, not square")
            w, h = size.oriented(self.orientation)
            if abs(self.photo_width_inches - w) > 0.01 or abs(self.photo_height_inches - h) > 0.01:
                raise ValueError(
                    "photo_width/height_inches must match size_id in the given orientation"
                )
        if self.frame_id is None:
            self.frame_id = self.size_id or "custom"
        return self


class LayoutMetadataSchema(BaseModel):
    """Planner layout settings saved with a version (all optional)."""

    style: LayoutStyleId | None = None
    gap_inches: float | None = Field(default=None, ge=RULES.gap_min_inches, le=RULES.gap_max_inches)
    gap_unit: Literal["in", "cm"] | None = None
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    variant: int | None = Field(default=None, ge=0, lt=RULES.variant_count)

    model_config = ConfigDict(extra="forbid")


class PreviewFlagsSchema(BaseModel):
    """Planner preview toggles. `sofa` also selects the sofa clearance used for validation."""

    sofa: bool | None = None
    index_badges: bool | None = None
    guides: bool | None = None

    model_config = ConfigDict(extra="forbid")


class SaveDesignVersionRequest(BaseModel):
    """Payload for creating an immutable design version snapshot (EP-DSGN-02)."""

    layout_type: LayoutTypeId = Field(
        default="custom",
        max_length=50,
        description="custom, grid, salon, centre or row (legacy names are normalised)",
    )
    template_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9-]{1,64}$",
        description="Template slug (e.g. balanced-grid) or template ID the layout came from",
    )
    items: list[DesignItemInputSchema] = Field(
        min_length=RULES.frame_count_min,
        max_length=RULES.frame_count_max,
        description="1 to 16 placed frames",
    )
    layout_metadata: LayoutMetadataSchema | None = Field(
        default=None,
        description="Optional layout settings: style, gap_inches, gap_unit, seed, variant",
    )
    preview: PreviewFlagsSchema | None = Field(
        default=None,
        description="Optional preview flags: sofa, index_badges, guides",
    )

    @model_validator(mode="after")
    def _unique_items(self) -> "SaveDesignVersionRequest":
        ids = [item.item_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("item_id values must be unique within a version")
        return self


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
    matting: MattingOut
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
    wall: DesignWallOut
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
    wall: DesignWallOut
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
    wall: DesignWallOut
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
