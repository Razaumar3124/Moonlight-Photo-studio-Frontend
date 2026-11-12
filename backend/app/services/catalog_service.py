from bson import ObjectId

from app.core.exceptions import ValidationException
from app.modules import catalog
from app.repositories.catalog_repository import CatalogRepository
from app.schemas.catalog import (
    FrameColorOut,
    FrameFinishOut,
    FrameMaterialOut,
    FrameMaterialsListResponse,
    FrameMoldingOut,
    FrameSizeOut,
    FramesListResponse,
    LayoutStyleOut,
    PlannerCatalogResponse,
    PlannerRulesOut,
    RangeOut,
    SwatchOut,
)


def build_planner_catalog() -> PlannerCatalogResponse:
    """The static planner catalog (app/modules/catalog.py) as an API response."""
    rules = catalog.RULES
    return PlannerCatalogResponse(
        version=catalog.CATALOG_VERSION,
        frame_sizes=[
            FrameSizeOut(
                id=s.id,
                label=s.label,
                width_inches=s.width_inches,
                height_inches=s.height_inches,
                recommended=s.recommended,
            )
            for s in catalog.FRAME_SIZES
        ],
        frame_finishes=[
            FrameFinishOut(id=f.id, label=f.label, hex=f.hex, profile_inches=f.profile_inches)
            for f in catalog.FRAME_FINISHES
        ],
        mount_colors=[SwatchOut(id=m.id, label=m.label, hex=m.hex) for m in catalog.MOUNT_COLOURS],
        paint_shades=[SwatchOut(id=p.id, label=p.label, hex=p.hex) for p in catalog.PAINT_SHADES],
        layout_styles=[
            LayoutStyleOut(id=style_id, label=label)
            for style_id, label in catalog.LAYOUT_STYLE_LABELS.items()
        ],
        template_ids=list(catalog.TEMPLATE_IDS),
        wall_units=list(catalog.WALL_UNITS),
        gap_units=list(catalog.GAP_UNITS),
        rules=PlannerRulesOut(
            eye_level_inches=rules.eye_level_inches,
            wall_margin_inches=rules.wall_margin_inches,
            min_bottom_inches=rules.min_bottom_inches,
            sofa_top_from_floor_inches=round(rules.sofa_top_from_floor_inches, 4),
            sofa_clearance_inches=rules.sofa_clearance_inches,
            wall_width_inches=RangeOut(
                min=rules.wall_width_min_inches, max=rules.wall_width_max_inches
            ),
            wall_height_inches=RangeOut(
                min=rules.wall_height_min_inches, max=rules.wall_height_max_inches
            ),
            gap_inches=RangeOut(min=rules.gap_min_inches, max=rules.gap_max_inches),
            mat_inches=RangeOut(min=rules.mat_min_inches, max=rules.mat_max_inches),
            mat_step_inches=rules.mat_step_inches,
            frame_count=RangeOut(min=rules.frame_count_min, max=rules.frame_count_max),
            variant_count=rules.variant_count,
        ),
    )


class CatalogService:
    """Domain business logic for frame materials and frame moldings catalogs."""

    def __init__(self, catalog_repo: CatalogRepository) -> None:
        self.catalog_repo = catalog_repo

    async def get_frame_materials(
        self,
        category: str | None = None,
        available_only: bool = True,
    ) -> FrameMaterialsListResponse:
        """Retrieve list of available frame materials with optional category filtering."""
        if category:
            cat_norm = category.lower().strip()
            if cat_norm not in ("wood", "metal", "synthetic"):
                raise ValidationException(
                    message=(
                        f"Invalid material category '{category}'. "
                        "Must be 'wood', 'metal', or 'synthetic'."
                    ),
                    details=[
                        {
                            "field": "category",
                            "issue": "Must be one of: wood, metal, synthetic",
                        }
                    ],
                )
            category = cat_norm

        materials = await self.catalog_repo.list_materials(
            category=category,
            available_only=available_only,
        )

        items = [
            FrameMaterialOut(
                id=m.id,
                code=m.code,
                name=m.name,
                category=m.category,
                finish=m.finish,
                base_price_per_linear_inch=m.base_price_per_linear_inch,
                waste_factor_percentage=m.waste_factor_percentage,
                thumbnail_url=m.thumbnail_url,
                is_available=m.is_available,
            )
            for m in materials
        ]
        return FrameMaterialsListResponse(items=items, total=len(items))

    async def get_frames(
        self,
        material_id: str | None = None,
        color: str | None = None,
        min_width: float | None = None,
        max_width: float | None = None,
    ) -> FramesListResponse:
        """Retrieve list of frame molding profiles matching criteria."""
        if material_id:
            material_id = material_id.strip()
            if not ObjectId.is_valid(material_id):
                raise ValidationException(
                    message=(
                        "Invalid material_id format; must be a 24-character hexadecimal ObjectId."
                    ),
                    details=[
                        {
                            "field": "material_id",
                            "issue": "Invalid ObjectId format",
                        }
                    ],
                )

        if min_width is not None and min_width < 0:
            raise ValidationException(
                message="min_width cannot be negative.",
                details=[{"field": "min_width", "issue": "Must be >= 0"}],
            )

        if max_width is not None and max_width < 0:
            raise ValidationException(
                message="max_width cannot be negative.",
                details=[{"field": "max_width", "issue": "Must be >= 0"}],
            )

        if min_width is not None and max_width is not None and min_width > max_width:
            raise ValidationException(
                message="min_width cannot be greater than max_width.",
                details=[
                    {
                        "field": "min_width",
                        "issue": f"min_width ({min_width}) exceeds max_width ({max_width})",
                    }
                ],
            )

        moldings = await self.catalog_repo.list_moldings(
            material_id=material_id,
            color=color,
            min_width=min_width,
            max_width=max_width,
            active_only=True,
        )

        items = [
            FrameMoldingOut(
                id=m.id,
                sku=m.sku,
                name=m.name,
                material_id=m.material_id,
                material_name=m.material_name,
                profile_width_inches=m.profile_width_inches,
                profile_depth_inches=m.profile_depth_inches,
                rabbet_depth_inches=m.rabbet_depth_inches,
                price_per_linear_inch=m.price_per_linear_inch,
                available_colors=[
                    FrameColorOut(
                        id=c.id,
                        name=c.name,
                        hex=c.hex,
                        profile_in=c.profile_in,
                    )
                    for c in m.available_colors
                ],
                thumbnail_url=m.thumbnail_url,
                is_active=m.is_active,
            )
            for m in moldings
        ]
        return FramesListResponse(items=items, total=len(items))
