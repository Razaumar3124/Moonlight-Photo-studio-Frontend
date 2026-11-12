from pydantic import BaseModel, ConfigDict, Field


class FrameMaterialOut(BaseModel):
    """Public frame material representation conforming to EP-CAT-01."""

    id: str = Field(description="Unique material identifier")
    code: str = Field(description="Unique material stock code")
    name: str = Field(description="Material display name")
    category: str = Field(description="Material classification (wood, metal, synthetic)")
    finish: str = Field(description="Surface finish description")
    base_price_per_linear_inch: str = Field(
        description="Fixed 2-decimal string price per linear inch"
    )
    waste_factor_percentage: float = Field(description="Cutting scrap waste factor percentage")
    thumbnail_url: str = Field(description="Preview image path")
    is_available: bool = Field(description="Inventory availability flag")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "672520012e5c6a1b2c3d4e01",
                "code": "NAT-OAK-01",
                "name": "Natural White Oak",
                "category": "wood",
                "finish": "Natural Satin",
                "base_price_per_linear_inch": "14.50",
                "waste_factor_percentage": 15.0,
                "thumbnail_url": "/static/materials/natural-oak.webp",
                "is_available": True,
            }
        },
    )


class FrameMaterialsListResponse(BaseModel):
    """Collection response containing frame materials and total count."""

    items: list[FrameMaterialOut] = Field(default_factory=list)
    total: int = Field(description="Total count of matching material records")


class FrameColorOut(BaseModel):
    """Frame color swatch with visual hex code and face profile width."""

    id: str = Field(
        description="Stable finish ID (e.g. natural-oak); wood finishes match GET /catalog"
    )
    name: str = Field(description="Color display name (e.g. Natural Oak, Walnut)")
    hex: str = Field(description="6-character hex color code (e.g. #916843)")
    profile_in: float = Field(description="Face width profile in inches")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "natural-oak",
                "name": "Natural Oak",
                "hex": "#916843",
                "profile_in": 1.0,
            }
        },
    )


class FrameMoldingOut(BaseModel):
    """Public frame molding profile representation conforming to EP-CAT-02."""

    id: str = Field(description="Unique frame profile identifier")
    sku: str = Field(description="Commercial stock-keeping unit")
    name: str = Field(description="Commercial profile name")
    material_id: str = Field(description="Foreign reference to parent frame_materials ID")
    material_name: str = Field(description="Denormalized material display name")
    profile_width_inches: float = Field(description="Visible face width in inches")
    profile_depth_inches: float = Field(description="Total depth off wall in inches")
    rabbet_depth_inches: float = Field(
        description="Internal glass/mat/photo cavity depth in inches"
    )
    price_per_linear_inch: str = Field(description="Fixed 2-decimal string price per linear inch")
    available_colors: list[FrameColorOut] = Field(
        default_factory=list,
        description="List of available color finishes with hex codes",
    )
    thumbnail_url: str = Field(description="Profile thumbnail image path")
    is_active: bool = Field(description="Active catalog status flag")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "672521012e5c6a1b2c3d4f01",
                "sku": "MOLD-OAK-BOX-100",
                "name": "Natural Oak Modern Box",
                "material_id": "672520012e5c6a1b2c3d4e01",
                "material_name": "Natural White Oak",
                "profile_width_inches": 1.0,
                "profile_depth_inches": 1.5,
                "rabbet_depth_inches": 0.75,
                "price_per_linear_inch": "22.00",
                "available_colors": [
                    {
                        "id": "natural-oak",
                        "name": "Natural Oak",
                        "hex": "#916843",
                        "profile_in": 1.0,
                    },
                    {"id": "walnut", "name": "Walnut", "hex": "#784E2D", "profile_in": 1.0},
                    {"id": "ivory", "name": "Ivory", "hex": "#FAF3E8", "profile_in": 0.875},
                ],
                "thumbnail_url": "/static/frames/oak-box.webp",
                "is_active": True,
            }
        },
    )


class FramesListResponse(BaseModel):
    """Collection response containing frame moldings and total count."""

    items: list[FrameMoldingOut] = Field(default_factory=list)
    total: int = Field(description="Total count of matching frame profile records")


# --------------------------- Planner catalog (GET /catalog) ---------------------------


class FrameSizeOut(BaseModel):
    """Photo opening, portrait orientation (short side first). Landscape swaps the sides."""

    id: str = Field(description="Stable size ID, e.g. 12x16")
    label: str
    width_inches: float
    height_inches: float
    recommended: bool = False


class FrameFinishOut(BaseModel):
    id: str = Field(description="Stable finish ID, e.g. natural-oak")
    label: str
    hex: str
    profile_inches: float = Field(description="Visible moulding face width added on each side")


class SwatchOut(BaseModel):
    id: str
    label: str
    hex: str


class LayoutStyleOut(BaseModel):
    id: str = Field(description="grid, salon, centre or row")
    label: str


class RangeOut(BaseModel):
    min: float
    max: float


class PlannerRulesOut(BaseModel):
    """Physical planner rules in inches. Server-side validation uses exactly these values."""

    eye_level_inches: float
    wall_margin_inches: float
    min_bottom_inches: float
    sofa_top_from_floor_inches: float
    sofa_clearance_inches: float
    wall_width_inches: RangeOut
    wall_height_inches: RangeOut
    gap_inches: RangeOut
    mat_inches: RangeOut
    mat_step_inches: float
    frame_count: RangeOut
    variant_count: int


class PlannerCatalogResponse(BaseModel):
    """Every option and rule of the Memory Wall planner, with stable IDs."""

    version: str = Field(description="Catalog revision date (YYYY-MM-DD)")
    frame_sizes: list[FrameSizeOut]
    frame_finishes: list[FrameFinishOut]
    mount_colors: list[SwatchOut]
    paint_shades: list[SwatchOut]
    layout_styles: list[LayoutStyleOut]
    template_ids: list[str]
    wall_units: list[str] = Field(description="Units the planner offers (API values are inches)")
    gap_units: list[str]
    rules: PlannerRulesOut
