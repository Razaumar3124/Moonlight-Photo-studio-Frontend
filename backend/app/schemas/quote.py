"""Pydantic request and response schemas for WhatsApp quote preparation and reports."""

from datetime import datetime

from pydantic import BaseModel, Field


class QuoteMountInput(BaseModel):
    """Mount / matboard configuration input from frontend."""

    enabled: bool = Field(default=True, description="Whether matboard border is enabled")
    colour_id: str | None = Field(default=None, alias="colourId")
    margin_in: float = Field(default=2.0, ge=0.0, alias="marginIn")

    model_config = {"populate_by_name": True}


class QuotePhotoInput(BaseModel):
    """Photo assignment input from frontend."""

    kind: str = Field(description="Photo source kind: sample, upload, or none")
    sample_id: str | None = Field(default=None, alias="sampleId")
    photo_id: str | None = Field(default=None, alias="photoId")
    name: str | None = None
    url: str | None = None

    model_config = {"populate_by_name": True}


class QuoteFrameInput(BaseModel):
    """Individual frame configuration input."""

    id: str = Field(description="Frame client-side identifier")
    size_id: str = Field(alias="sizeId", description="Standard size key (e.g. 12x16)")
    orientation: str = Field(
        default="portrait", description="Orientation: portrait, landscape, square"
    )
    finish_id: str = Field(alias="finishId", description="Moulding finish key (e.g. natural-oak)")
    mount: QuoteMountInput = Field(default_factory=QuoteMountInput)
    photo: QuotePhotoInput | None = None
    position_x_in: float | None = Field(default=None, alias="x")
    position_y_in: float | None = Field(default=None, alias="y")

    model_config = {"populate_by_name": True}


class QuoteWallInput(BaseModel):
    """Wall dimension and styling configuration input."""

    width_in: float = Field(gt=0.0, alias="widthIn", description="Wall width in inches")
    height_in: float = Field(gt=0.0, alias="heightIn", description="Wall height in inches")
    paint_id: str | None = Field(default=None, alias="paintId")
    color_hex: str = Field(default="#F0EBE4", alias="colorHex")
    texture: str | None = None
    display_unit: str = Field(default="in", alias="displayUnit")
    has_sofa: bool = Field(default=False, alias="hasSofa")

    model_config = {"populate_by_name": True}


class QuoteLayoutInput(BaseModel):
    """Arrangement layout settings."""

    style: str = Field(
        default="grid", description="Layout style (grid, salon, centre, row, custom)"
    )
    gap_in: float = Field(default=2.0, ge=0.0, alias="gapIn")

    model_config = {"populate_by_name": True}


class QuotePrepareInput(BaseModel):
    """Planner design state payload captured from frontend memory wall."""

    title: str = Field(default="Memory Wall Design", description="Human-readable title")
    design_id: str | None = Field(
        default=None, alias="designId", description="Optional saved design ObjectId"
    )
    wall: QuoteWallInput
    layout: QuoteLayoutInput = Field(default_factory=QuoteLayoutInput)
    frames: list[QuoteFrameInput] = Field(min_length=1, max_length=50, description="List of frames")

    model_config = {"populate_by_name": True}


class QuotePrepareResponse(BaseModel):
    """Response returned upon successful quote request preparation."""

    quote_id: str = Field(description="Unique quote reference (e.g., SQ-2026-0012)")
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
    report_url: str
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
