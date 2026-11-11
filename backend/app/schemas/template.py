from pydantic import BaseModel, ConfigDict, Field


class TemplateSlotOut(BaseModel):
    """Layout template photo slot geometry relative to arrangement wall."""

    slot_id: str = Field(description="Slot identifier (e.g. slot-1)")
    relative_x_ratio: float = Field(
        description="Relative horizontal anchor ratio across wall width (0.0 to 1.0)"
    )
    relative_y_ratio: float = Field(
        description="Relative vertical anchor ratio down wall height (0.0 to 1.0)"
    )
    default_photo_width_inches: float = Field(
        description="Default recommended photo opening width in inches"
    )
    default_photo_height_inches: float = Field(
        description="Default recommended photo opening height in inches"
    )
    aspect_ratio: float = Field(description="Width to height ratio (width / height)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "slot_id": "slot-1",
                "relative_x_ratio": 0.25,
                "relative_y_ratio": 0.25,
                "default_photo_width_inches": 12.0,
                "default_photo_height_inches": 16.0,
                "aspect_ratio": 0.75,
            }
        },
    )


class LayoutTemplateOut(BaseModel):
    """Pre-engineered gallery wall template conforming to EP-TMPL-01."""

    id: str = Field(description="Unique template identifier")
    slug: str = Field(description="URL and frontend friendly identifier (e.g. balanced-grid)")
    name: str = Field(description="Display title of the layout template")
    description: str = Field(description="Editorial description of the arrangement")
    category: str = Field(description="Layout category (grid, salon, centre, row, triptych, etc.)")
    min_wall_width_inches: float = Field(description="Minimum wall width required in inches")
    min_wall_height_inches: float = Field(description="Minimum wall height required in inches")
    recommended_wall_width_inches: float = Field(
        description="Recommended ideal wall width in inches"
    )
    recommended_wall_height_inches: float = Field(
        description="Recommended ideal wall height in inches"
    )
    slots_count: int = Field(description="Total number of frame slots in arrangement")
    slots: list[TemplateSlotOut] = Field(
        default_factory=list,
        description="Array of frame slot positions and default dimensions",
    )
    thumbnail_url: str = Field(description="Preview diagram / image path")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "672522012e5c6a1b2c3d5001",
                "slug": "balanced-grid",
                "name": "Balanced Grid",
                "description": "Nine Atelier Classic frames in a calm, even 3 x 3 grid.",
                "category": "grid",
                "min_wall_width_inches": 80.0,
                "min_wall_height_inches": 60.0,
                "recommended_wall_width_inches": 120.0,
                "recommended_wall_height_inches": 96.0,
                "slots_count": 9,
                "slots": [
                    {
                        "slot_id": "slot-1",
                        "relative_x_ratio": 0.25,
                        "relative_y_ratio": 0.25,
                        "default_photo_width_inches": 12.0,
                        "default_photo_height_inches": 16.0,
                        "aspect_ratio": 0.75,
                    }
                ],
                "thumbnail_url": "/static/templates/balanced-grid.webp",
            }
        },
    )


class TemplatesListResponse(BaseModel):
    """Collection response containing gallery wall templates and total count."""

    items: list[LayoutTemplateOut] = Field(default_factory=list)
    total: int = Field(description="Total count of matching template records")
