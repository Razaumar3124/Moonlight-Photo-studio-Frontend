"""Pydantic request and response schemas for WhatsApp quote preparation and reports.

`design_data` is the planner's own state (frontend `PlannerState`, camelCase). Snake_case
names are accepted too. Catalog IDs (sizes, finishes, mount colours, paint shades) are
validated against app/modules/catalog.py; unknown IDs are rejected rather than guessed.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules import catalog
from app.modules.catalog import (
    RULES,
    DisplayUnit,
    FinishId,
    FrameSizeId,
    LayoutTypeId,
    MountColourId,
    PaintShadeId,
)


class QuoteMountInput(BaseModel):
    """Mount / matboard configuration input from frontend."""

    enabled: bool = Field(default=True, description="Whether matboard border is enabled")
    colour_id: MountColourId | None = Field(default=None, alias="colourId")
    margin_in: float = Field(
        default=2.0, ge=RULES.mat_min_inches, le=RULES.mat_max_inches, alias="marginIn"
    )

    model_config = {"populate_by_name": True}


class QuotePhotoInput(BaseModel):
    """Photo assignment input from frontend (session object URLs are ignored)."""

    kind: Literal["sample", "upload", "none"] = Field(description="sample, upload or none")
    sample_id: str | None = Field(
        default=None, alias="sampleId", pattern=r"^[a-z0-9][a-z0-9-]{0,49}$"
    )
    photo_id: str | None = Field(default=None, alias="photoId", pattern=r"^[0-9a-fA-F]{24}$")
    name: str | None = Field(default=None, max_length=120)

    model_config = {"populate_by_name": True}


class QuoteFrameInput(BaseModel):
    """Individual frame configuration input."""

    id: str = Field(min_length=1, max_length=64, description="Frame client-side identifier")
    size_id: FrameSizeId = Field(alias="sizeId", description="Catalog size ID (e.g. 12x16)")
    orientation: Literal["portrait", "landscape"] = Field(default="portrait")
    finish_id: FinishId = Field(alias="finishId", description="Catalog finish ID (e.g. walnut)")
    mount: QuoteMountInput = Field(default_factory=QuoteMountInput)
    photo: QuotePhotoInput | None = None
    position_x_in: float | None = Field(default=None, ge=0.0, alias="x")
    position_y_in: float | None = Field(default=None, ge=0.0, alias="y")

    model_config = {"populate_by_name": True}


class QuoteWallInput(BaseModel):
    """Wall dimension and styling configuration input."""

    width_in: float = Field(
        ge=RULES.wall_width_min_inches,
        le=RULES.wall_width_max_inches,
        alias="widthIn",
        description="Wall width in inches (36–480)",
    )
    height_in: float = Field(
        ge=RULES.wall_height_min_inches,
        le=RULES.wall_height_max_inches,
        alias="heightIn",
        description="Wall height in inches (48–240)",
    )
    paint_id: PaintShadeId | None = Field(default=None, alias="paintId")
    color_hex: str = Field(
        default="#F0EBE4", alias="colorHex", pattern=r"^#(?:[0-9a-fA-F]{3}){1,2}$"
    )
    texture: str | None = Field(default=None, max_length=50)
    # Older payloads put these on the wall; the planner keeps them at the top level.
    display_unit: DisplayUnit | None = Field(default=None, alias="displayUnit")
    has_sofa: bool | None = Field(default=None, alias="hasSofa")

    model_config = {"populate_by_name": True}


class QuoteLayoutInput(BaseModel):
    """Arrangement layout settings."""

    style: LayoutTypeId = Field(default="grid", description="grid, salon, centre, row or custom")
    gap_in: float = Field(
        default=3.0, ge=RULES.gap_min_inches, le=RULES.gap_max_inches, alias="gapIn"
    )

    model_config = {"populate_by_name": True}


class QuotePreviewInput(BaseModel):
    sofa: bool | None = None


class QuotePrepareInput(BaseModel):
    """Planner design state payload captured from frontend memory wall."""

    title: str = Field(default="Memory Wall Design", max_length=100, description="Design title")
    design_id: str | None = Field(
        default=None,
        alias="designId",
        pattern=r"^[0-9a-fA-F]{24}$",
        description="Optional saved design ID",
    )
    display_unit: DisplayUnit | None = Field(default=None, alias="displayUnit")
    preview: QuotePreviewInput | None = None
    wall: QuoteWallInput
    layout: QuoteLayoutInput = Field(default_factory=QuoteLayoutInput)
    frames: list[QuoteFrameInput] = Field(
        min_length=RULES.frame_count_min,
        max_length=RULES.frame_count_max,
        description="1 to 16 frames",
    )

    model_config = {"populate_by_name": True}

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str) -> str:
        return " ".join(v.split()) or "Memory Wall Design"

    @property
    def effective_display_unit(self) -> str:
        return self.display_unit or self.wall.display_unit or "in"

    @property
    def effective_has_sofa(self) -> bool:
        if self.wall.has_sofa is not None:
            return self.wall.has_sofa
        return bool(self.preview and self.preview.sofa)

    @property
    def effective_color_hex(self) -> str:
        shade = catalog.get_paint_shade(self.wall.paint_id)
        return shade.hex if shade else self.wall.color_hex


class QuotePrepareResponse(BaseModel):
    """Response returned upon successful quote request preparation."""

    quote_id: str = Field(description="Unique quote reference (e.g., MQ-2026-0012)")
    status: str = Field(default="draft", description="Quote status")
    whatsapp_url: str = Field(
        description="Official Click-to-Chat URL ready for client browser launch"
    )
    report_url: str = Field(description="Secure, unguessable digital design report link")
    expires_at: datetime = Field(description="UTC timestamp when share link expires")


class QuoteFrameSummaryOut(BaseModel):
    """Specification of a frame for display in digital report."""

    number: int
    size: str
    dimensions: str
    orientation: str
    finish: str
    mount: str
    photo: str | None = None


class QuoteDetailResponse(BaseModel):
    """Authorized quote details response for the owner customer."""

    quote_id: str
    status: str
    design_title: str
    layout_style: str
    wall_size: str
    frame_count: int
    finish_summary: str
    report_url: str | None = Field(
        default=None,
        description=(
            "Always null: the share link is only returned by POST /quotes/prepare (the server "
            "stores just a hash of its token)"
        ),
    )
    preview_url: str
    customer_name: str
    customer_phone: str | None = None
    customer_email: str
    frames: list[QuoteFrameSummaryOut]
    expires_at: datetime
    created_at: datetime


class QuoteShareResponse(BaseModel):
    """Public read-only digital design report JSON response."""

    quote_id: str
    created_at: str
    expires_at: str
    customer_name: str
    customer_contact_masked: str
    design_title: str
    layout_style: str
    wall_dimensions: str
    frame_count: int
    finish_summary: str
    preview_image_url: str
    frames: list[QuoteFrameSummaryOut]
