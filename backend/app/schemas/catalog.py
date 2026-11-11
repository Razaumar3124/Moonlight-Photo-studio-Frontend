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

    name: str = Field(description="Color display name (e.g. Natural Oak, Walnut)")
    hex: str = Field(description="6-character hex color code (e.g. #916843)")
    profile_in: float = Field(description="Face width profile in inches")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
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
                    {"name": "Natural Oak", "hex": "#916843", "profile_in": 1.0},
                    {"name": "Walnut", "hex": "#784E2D", "profile_in": 1.0},
                    {"name": "Ivory", "hex": "#FAF3E8", "profile_in": 0.875},
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
