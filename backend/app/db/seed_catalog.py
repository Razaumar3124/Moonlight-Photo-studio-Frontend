import argparse
import asyncio
import logging
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings
from app.db.mongodb import mongo_manager
from app.models.catalog import FrameColorOption, FrameMaterialInDB, FrameMoldingInDB
from app.models.template import LayoutTemplateInDB, TemplateSlotInDB
from app.repositories.catalog_repository import CatalogRepository
from app.repositories.template_repository import TemplateRepository

logger = logging.getLogger("saf_studio.seed")


def _slot(slot_id: str, x: float, y: float, w: float, h: float) -> dict[str, Any]:
    """Helper to construct slot definitions cleanly."""
    return {
        "slot_id": slot_id,
        "relative_x_ratio": x,
        "relative_y_ratio": y,
        "default_photo_width_inches": w,
        "default_photo_height_inches": h,
        "aspect_ratio": round(w / h, 4),
    }


# ---------------- Master Seed Data ----------------

SEED_MATERIALS: list[dict[str, Any]] = [
    {
        "code": "NAT-OAK-01",
        "name": "Natural White Oak",
        "category": "wood",
        "finish": "Natural Satin",
        "base_price_per_linear_inch": "14.50",
        "waste_factor_percentage": 15.0,
        "thumbnail_url": "/static/materials/natural-oak.webp",
        "is_available": True,
    },
    {
        "code": "TEAK-01",
        "name": "Premium Plantation Teak",
        "category": "wood",
        "finish": "Oiled Matte",
        "base_price_per_linear_inch": "18.00",
        "waste_factor_percentage": 15.0,
        "thumbnail_url": "/static/materials/teak-natural.webp",
        "is_available": True,
    },
    {
        "code": "ALUM-01",
        "name": "Anodized Aluminium",
        "category": "metal",
        "finish": "Brushed Metallic",
        "base_price_per_linear_inch": "12.00",
        "waste_factor_percentage": 10.0,
        "thumbnail_url": "/static/materials/anodized-aluminium.webp",
        "is_available": True,
    },
    {
        "code": "SYNTH-01",
        "name": "Engineered Polymer Composite",
        "category": "synthetic",
        "finish": "Smooth Matte",
        "base_price_per_linear_inch": "9.50",
        "waste_factor_percentage": 8.0,
        "thumbnail_url": "/static/materials/synthetic-polymer.webp",
        "is_available": True,
    },
]

# Exact 8 wood finishes from frontend WOOD_FINISHES constants
FRONTEND_WOOD_FINISHES = [
    {"name": "Walnut", "hex": "#784E2D", "profile_in": 1.0},
    {"name": "Natural Oak", "hex": "#916843", "profile_in": 1.0},
    {"name": "Ivory", "hex": "#FAF3E8", "profile_in": 0.875},
    {"name": "Whitewash", "hex": "#EEE6DE", "profile_in": 0.875},
    {"name": "Dark Teak", "hex": "#774B31", "profile_in": 1.0},
    {"name": "Honey", "hex": "#B1875F", "profile_in": 1.0},
    {"name": "Golden Teak", "hex": "#B07840", "profile_in": 1.125},
    {"name": "Mahogany", "hex": "#7A432D", "profile_in": 1.125},
]

SEED_MOLDINGS: list[dict[str, Any]] = [
    {
        "sku": "MOLD-OAK-BOX-100",
        "name": "Natural Oak Modern Box",
        "material_code": "NAT-OAK-01",
        "profile_width_inches": 1.0,
        "profile_depth_inches": 1.5,
        "rabbet_depth_inches": 0.75,
        "price_per_linear_inch": "22.00",
        "available_colors": FRONTEND_WOOD_FINISHES,
        "thumbnail_url": "/static/frames/oak-box.webp",
        "is_active": True,
    },
    {
        "sku": "MOLD-WOOD-CLASSIC-075",
        "name": "Atelier Classic Profile",
        "material_code": "TEAK-01",
        "profile_width_inches": 0.875,
        "profile_depth_inches": 1.25,
        "rabbet_depth_inches": 0.625,
        "price_per_linear_inch": "19.50",
        "available_colors": [
            {"name": "Ivory", "hex": "#FAF3E8", "profile_in": 0.875},
            {"name": "Whitewash", "hex": "#EEE6DE", "profile_in": 0.875},
            {"name": "Dark Teak", "hex": "#774B31", "profile_in": 1.0},
            {"name": "Honey", "hex": "#B1875F", "profile_in": 1.0},
        ],
        "thumbnail_url": "/static/frames/wood-classic.webp",
        "is_active": True,
    },
    {
        "sku": "MOLD-MET-SLIM-050",
        "name": "Slim Gallery Metal",
        "material_code": "ALUM-01",
        "profile_width_inches": 0.5,
        "profile_depth_inches": 1.0,
        "rabbet_depth_inches": 0.5,
        "price_per_linear_inch": "16.00",
        "available_colors": [
            {"name": "Matte Black", "hex": "#1D191A", "profile_in": 0.5},
            {"name": "Brushed Silver", "hex": "#C5C5C7", "profile_in": 0.5},
            {"name": "Champagne Gold", "hex": "#D4AF37", "profile_in": 0.5},
        ],
        "thumbnail_url": "/static/frames/metal-slim.webp",
        "is_active": True,
    },
    {
        "sku": "MOLD-SYN-MIN-075",
        "name": "Studio Minimalist Synthetic",
        "material_code": "SYNTH-01",
        "profile_width_inches": 0.75,
        "profile_depth_inches": 1.0,
        "rabbet_depth_inches": 0.5,
        "price_per_linear_inch": "12.50",
        "available_colors": [
            {"name": "Pure White", "hex": "#FFFFFF", "profile_in": 0.75},
            {"name": "Midnight Black", "hex": "#111111", "profile_in": 0.75},
        ],
        "thumbnail_url": "/static/frames/synthetic-minimal.webp",
        "is_active": True,
    },
]

# 10 gallery wall templates matching frontend TEMPLATES
SEED_TEMPLATES: list[dict[str, Any]] = [
    {
        "slug": "balanced-grid",
        "name": "Balanced Grid",
        "description": "Nine Atelier Classic frames in a calm, even 3 × 3 grid.",
        "category": "grid",
        "min_wall_width_inches": 80.0,
        "min_wall_height_inches": 60.0,
        "recommended_wall_width_inches": 120.0,
        "recommended_wall_height_inches": 96.0,
        "slots_count": 9,
        "slots": [
            _slot(
                f"slot-{i + 1}",
                round(0.35 + (i % 3) * 0.15, 3),
                round(0.38 + (i // 3) * 0.12, 3),
                12.0,
                16.0,
            )
            for i in range(9)
        ],
        "thumbnail_url": "/static/templates/balanced-grid.webp",
        "is_active": True,
    },
    {
        "slug": "creative-salon",
        "name": "Creative Salon",
        "description": "A relaxed cluster of mixed sizes and orientations, gallery-style.",
        "category": "salon",
        "min_wall_width_inches": 90.0,
        "min_wall_height_inches": 60.0,
        "recommended_wall_width_inches": 140.0,
        "recommended_wall_height_inches": 96.0,
        "slots_count": 11,
        "slots": [
            _slot("slot-1", 0.25, 0.35, 20.0, 16.0),
            _slot("slot-2", 0.42, 0.32, 11.0, 14.0),
            _slot("slot-3", 0.54, 0.30, 8.0, 10.0),
            _slot("slot-4", 0.65, 0.35, 12.0, 16.0),
            _slot("slot-5", 0.28, 0.52, 10.0, 8.0),
            _slot("slot-6", 0.38, 0.50, 5.0, 7.0),
            _slot("slot-7", 0.48, 0.52, 14.0, 11.0),
            _slot("slot-8", 0.60, 0.54, 8.0, 10.0),
            _slot("slot-9", 0.70, 0.50, 7.0, 5.0),
            _slot("slot-10", 0.32, 0.68, 12.0, 16.0),
            _slot("slot-11", 0.56, 0.68, 8.0, 10.0),
        ],
        "thumbnail_url": "/static/templates/creative-salon.webp",
        "is_active": True,
    },
    {
        "slug": "centre-focus",
        "name": "Centre Focus",
        "description": "One statement print framed by four smaller companions.",
        "category": "centre",
        "min_wall_width_inches": 75.0,
        "min_wall_height_inches": 55.0,
        "recommended_wall_width_inches": 110.0,
        "recommended_wall_height_inches": 90.0,
        "slots_count": 5,
        "slots": [
            _slot("slot-1", 0.50, 0.50, 30.0, 20.0),
            _slot("slot-2", 0.28, 0.40, 8.0, 10.0),
            _slot("slot-3", 0.28, 0.60, 8.0, 10.0),
            _slot("slot-4", 0.72, 0.40, 8.0, 10.0),
            _slot("slot-5", 0.72, 0.60, 8.0, 10.0),
        ],
        "thumbnail_url": "/static/templates/centre-focus.webp",
        "is_active": True,
    },
    {
        "slug": "minimal-row",
        "name": "Minimal Row",
        "description": "Four square-feeling frames on one clean line. Perfect above a sofa.",
        "category": "row",
        "min_wall_width_inches": 80.0,
        "min_wall_height_inches": 50.0,
        "recommended_wall_width_inches": 110.0,
        "recommended_wall_height_inches": 70.0,
        "slots_count": 4,
        "slots": [
            _slot("slot-1", 0.26, 0.50, 14.0, 11.0),
            _slot("slot-2", 0.42, 0.50, 14.0, 11.0),
            _slot("slot-3", 0.58, 0.50, 14.0, 11.0),
            _slot("slot-4", 0.74, 0.50, 14.0, 11.0),
        ],
        "thumbnail_url": "/static/templates/minimal-row.webp",
        "is_active": True,
    },
    {
        "slug": "classic-six",
        "name": "Classic Six",
        "description": "A 3 × 2 grid of 11 × 14 prints. Tidy and timeless.",
        "category": "grid",
        "min_wall_width_inches": 70.0,
        "min_wall_height_inches": 55.0,
        "recommended_wall_width_inches": 100.0,
        "recommended_wall_height_inches": 80.0,
        "slots_count": 6,
        "slots": [
            _slot("slot-1", 0.35, 0.42, 11.0, 14.0),
            _slot("slot-2", 0.50, 0.42, 11.0, 14.0),
            _slot("slot-3", 0.65, 0.42, 11.0, 14.0),
            _slot("slot-4", 0.35, 0.58, 11.0, 14.0),
            _slot("slot-5", 0.50, 0.58, 11.0, 14.0),
            _slot("slot-6", 0.65, 0.58, 11.0, 14.0),
        ],
        "thumbnail_url": "/static/templates/classic-six.webp",
        "is_active": True,
    },
    {
        "slug": "triptych",
        "name": "Triptych",
        "description": "Three tall prints that tell one story, left to right.",
        "category": "triptych",
        "min_wall_width_inches": 65.0,
        "min_wall_height_inches": 50.0,
        "recommended_wall_width_inches": 90.0,
        "recommended_wall_height_inches": 75.0,
        "slots_count": 3,
        "slots": [
            _slot("slot-1", 0.32, 0.50, 16.0, 20.0),
            _slot("slot-2", 0.50, 0.50, 16.0, 20.0),
            _slot("slot-3", 0.68, 0.50, 16.0, 20.0),
        ],
        "thumbnail_url": "/static/templates/triptych.webp",
        "is_active": True,
    },
    {
        "slug": "petite-salon",
        "name": "Petite Salon",
        "description": "Small frames, big charm. Ideal for hallways and stairs.",
        "category": "salon",
        "min_wall_width_inches": 65.0,
        "min_wall_height_inches": 50.0,
        "recommended_wall_width_inches": 95.0,
        "recommended_wall_height_inches": 75.0,
        "slots_count": 7,
        "slots": [
            _slot("slot-1", 0.35, 0.40, 8.0, 10.0),
            _slot("slot-2", 0.48, 0.38, 7.0, 5.0),
            _slot("slot-3", 0.60, 0.40, 5.0, 7.0),
            _slot("slot-4", 0.38, 0.55, 10.0, 8.0),
            _slot("slot-5", 0.52, 0.54, 5.0, 7.0),
            _slot("slot-6", 0.64, 0.56, 8.0, 10.0),
            _slot("slot-7", 0.48, 0.68, 7.0, 5.0),
        ],
        "thumbnail_url": "/static/templates/petite-salon.webp",
        "is_active": True,
    },
    {
        "slug": "statement-centre",
        "name": "Statement Centre",
        "description": "A large landscape hero with six petite frames on its wings.",
        "category": "centre",
        "min_wall_width_inches": 85.0,
        "min_wall_height_inches": 60.0,
        "recommended_wall_width_inches": 125.0,
        "recommended_wall_height_inches": 90.0,
        "slots_count": 7,
        "slots": [
            _slot("slot-1", 0.50, 0.50, 36.0, 24.0),
            _slot("slot-2", 0.28, 0.38, 5.0, 7.0),
            _slot("slot-3", 0.28, 0.50, 5.0, 7.0),
            _slot("slot-4", 0.28, 0.62, 5.0, 7.0),
            _slot("slot-5", 0.72, 0.38, 5.0, 7.0),
            _slot("slot-6", 0.72, 0.50, 5.0, 7.0),
            _slot("slot-7", 0.72, 0.62, 5.0, 7.0),
        ],
        "thumbnail_url": "/static/templates/statement-centre.webp",
        "is_active": True,
    },
    {
        "slug": "panorama-row",
        "name": "Panorama Row",
        "description": "Five landscape prints for long walls and corridors.",
        "category": "row",
        "min_wall_width_inches": 85.0,
        "min_wall_height_inches": 45.0,
        "recommended_wall_width_inches": 120.0,
        "recommended_wall_height_inches": 65.0,
        "slots_count": 5,
        "slots": [
            _slot("slot-1", 0.22, 0.50, 10.0, 8.0),
            _slot("slot-2", 0.36, 0.50, 10.0, 8.0),
            _slot("slot-3", 0.50, 0.50, 10.0, 8.0),
            _slot("slot-4", 0.64, 0.50, 10.0, 8.0),
            _slot("slot-5", 0.78, 0.50, 10.0, 8.0),
        ],
        "thumbnail_url": "/static/templates/panorama-row.webp",
        "is_active": True,
    },
    {
        "slug": "grand-quad",
        "name": "Grand Quad",
        "description": "Four large prints in a bold 2 × 2 block.",
        "category": "grid",
        "min_wall_width_inches": 65.0,
        "min_wall_height_inches": 60.0,
        "recommended_wall_width_inches": 95.0,
        "recommended_wall_height_inches": 90.0,
        "slots_count": 4,
        "slots": [
            _slot("slot-1", 0.38, 0.40, 16.0, 20.0),
            _slot("slot-2", 0.62, 0.40, 16.0, 20.0),
            _slot("slot-3", 0.38, 0.60, 16.0, 20.0),
            _slot("slot-4", 0.62, 0.60, 16.0, 20.0),
        ],
        "thumbnail_url": "/static/templates/grand-quad.webp",
        "is_active": True,
    },
]


async def seed_catalogs_and_templates(
    db: AsyncDatabase,
    overwrite: bool = False,
) -> dict[str, int]:
    """
    Idempotent seeder loading catalog materials, moldings, and templates into MongoDB.

    If overwrite is False, existing documents with matching unique keys (code, sku, slug)
    are untouched. If overwrite is True, definitions are updated while preserving IDs.
    """
    catalog_repo = CatalogRepository(db)
    template_repo = TemplateRepository(db)

    # 1. Ensure indexes
    await catalog_repo.create_indexes()
    await template_repo.create_indexes()

    materials_count = 0
    moldings_count = 0
    templates_count = 0

    # 2. Seed materials
    material_id_map: dict[str, str] = {}
    for mat_data in SEED_MATERIALS:
        existing = await catalog_repo.get_material_by_code(mat_data["code"])
        if existing:
            mat_id = existing.id
            if overwrite:
                updated = FrameMaterialInDB(id=mat_id, **mat_data)
                await catalog_repo.upsert_material(updated, overwrite=True)
        else:
            new_mat = FrameMaterialInDB(**mat_data)
            saved = await catalog_repo.upsert_material(new_mat, overwrite=False)
            mat_id = saved.id
        material_id_map[mat_data["code"]] = mat_id
        materials_count += 1

    # 3. Seed moldings
    for mold_data in SEED_MOLDINGS:
        mat_code = mold_data["material_code"]
        parent_mat_id = material_id_map.get(mat_code)
        if not parent_mat_id:
            parent_mat = await catalog_repo.get_material_by_code(mat_code)
            parent_mat_id = parent_mat.id if parent_mat else str(ObjectId())

        parent_mat = await catalog_repo.get_material_by_code(mat_code)
        mat_name = parent_mat.name if parent_mat else "Solid Wood"

        colors = [FrameColorOption(**c) for c in mold_data["available_colors"]]

        existing_molding = await catalog_repo.get_molding_by_sku(mold_data["sku"])
        if existing_molding:
            molding_id = existing_molding.id
            if overwrite:
                updated_molding = FrameMoldingInDB(
                    id=molding_id,
                    sku=mold_data["sku"],
                    name=mold_data["name"],
                    material_id=parent_mat_id,
                    material_name=mat_name,
                    profile_width_inches=mold_data["profile_width_inches"],
                    profile_depth_inches=mold_data["profile_depth_inches"],
                    rabbet_depth_inches=mold_data["rabbet_depth_inches"],
                    price_per_linear_inch=mold_data["price_per_linear_inch"],
                    available_colors=colors,
                    thumbnail_url=mold_data["thumbnail_url"],
                    is_active=mold_data["is_active"],
                )
                await catalog_repo.upsert_molding(updated_molding, overwrite=True)
        else:
            new_molding = FrameMoldingInDB(
                sku=mold_data["sku"],
                name=mold_data["name"],
                material_id=parent_mat_id,
                material_name=mat_name,
                profile_width_inches=mold_data["profile_width_inches"],
                profile_depth_inches=mold_data["profile_depth_inches"],
                rabbet_depth_inches=mold_data["rabbet_depth_inches"],
                price_per_linear_inch=mold_data["price_per_linear_inch"],
                available_colors=colors,
                thumbnail_url=mold_data["thumbnail_url"],
                is_active=mold_data["is_active"],
            )
            await catalog_repo.upsert_molding(new_molding, overwrite=False)
        moldings_count += 1

    # 4. Seed layout templates
    for tmpl_data in SEED_TEMPLATES:
        slots = [TemplateSlotInDB(**s) for s in tmpl_data["slots"]]
        existing_tmpl = await template_repo.get_template_by_slug(tmpl_data["slug"])
        if existing_tmpl:
            tmpl_id = existing_tmpl.id
            if overwrite:
                updated_tmpl = LayoutTemplateInDB(
                    id=tmpl_id,
                    slug=tmpl_data["slug"],
                    name=tmpl_data["name"],
                    description=tmpl_data["description"],
                    category=tmpl_data["category"],
                    min_wall_width_inches=tmpl_data["min_wall_width_inches"],
                    min_wall_height_inches=tmpl_data["min_wall_height_inches"],
                    recommended_wall_width_inches=tmpl_data["recommended_wall_width_inches"],
                    recommended_wall_height_inches=tmpl_data["recommended_wall_height_inches"],
                    slots_count=tmpl_data["slots_count"],
                    slots=slots,
                    thumbnail_url=tmpl_data["thumbnail_url"],
                    is_active=tmpl_data["is_active"],
                )
                await template_repo.upsert_template(updated_tmpl, overwrite=True)
        else:
            new_tmpl = LayoutTemplateInDB(
                slug=tmpl_data["slug"],
                name=tmpl_data["name"],
                description=tmpl_data["description"],
                category=tmpl_data["category"],
                min_wall_width_inches=tmpl_data["min_wall_width_inches"],
                min_wall_height_inches=tmpl_data["min_wall_height_inches"],
                recommended_wall_width_inches=tmpl_data["recommended_wall_width_inches"],
                recommended_wall_height_inches=tmpl_data["recommended_wall_height_inches"],
                slots_count=tmpl_data["slots_count"],
                slots=slots,
                thumbnail_url=tmpl_data["thumbnail_url"],
                is_active=tmpl_data["is_active"],
            )
            await template_repo.upsert_template(new_tmpl, overwrite=False)
        templates_count += 1

    logger.info(
        "Seeding complete: %d materials, %d moldings, %d templates",
        materials_count,
        moldings_count,
        templates_count,
    )
    return {
        "materials_seeded": materials_count,
        "moldings_seeded": moldings_count,
        "templates_seeded": templates_count,
    }


async def main() -> None:
    """CLI entrypoint for standalone catalog seeding."""
    parser = argparse.ArgumentParser(description="SAF Studio Catalog & Template Seeder")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing catalog records with initial values",
    )
    args = parser.parse_args()

    settings = get_settings()
    await mongo_manager.connect(settings)
    db = mongo_manager.get_database()
    try:
        result = await seed_catalogs_and_templates(db, overwrite=args.overwrite)
        print(f"Catalog seeding successfully finished: {result}")
    finally:
        await mongo_manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
