import re
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, IndexModel
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from app.models.catalog import FrameMaterialInDB, FrameMoldingInDB


class CatalogRepository:
    """Data access repository for frame materials and frame moldings collections."""

    def __init__(self, db: AsyncDatabase) -> None:
        self.materials_col: AsyncCollection = db["frame_materials"]
        self.moldings_col: AsyncCollection = db["frame_moldings"]

    async def create_indexes(self) -> None:
        """Create necessary indexes for catalog collections idempotently."""
        materials_indexes = [
            IndexModel([("code", ASCENDING)], unique=True, name="idx_materials_code"),
            IndexModel(
                [("category", ASCENDING), ("is_available", ASCENDING)],
                name="idx_materials_category",
            ),
        ]
        await self.materials_col.create_indexes(materials_indexes)

        moldings_indexes = [
            IndexModel([("sku", ASCENDING)], unique=True, name="idx_moldings_sku"),
            IndexModel(
                [("material_id", ASCENDING), ("is_active", ASCENDING)],
                name="idx_moldings_material",
            ),
        ]
        await self.moldings_col.create_indexes(moldings_indexes)

    # ---------------- Frame Materials ----------------

    async def list_materials(
        self,
        category: str | None = None,
        available_only: bool = True,
    ) -> list[FrameMaterialInDB]:
        """Query frame materials with optional category and availability filters."""
        query: dict[str, Any] = {}
        if available_only:
            query["is_available"] = True
        if category:
            query["category"] = category.lower().strip()

        cursor = self.materials_col.find(query).sort("name", ASCENDING)
        items: list[FrameMaterialInDB] = []
        async for doc in cursor:
            items.append(FrameMaterialInDB(**doc))
        return items

    async def get_material_by_id(self, material_id: str) -> FrameMaterialInDB | None:
        """Find frame material by string ObjectId."""
        if not ObjectId.is_valid(material_id):
            return None
        doc = await self.materials_col.find_one({"_id": ObjectId(material_id)})
        return FrameMaterialInDB(**doc) if doc else None

    async def get_material_by_code(self, code: str) -> FrameMaterialInDB | None:
        """Find frame material by unique stock code."""
        doc = await self.materials_col.find_one({"code": code.strip()})
        return FrameMaterialInDB(**doc) if doc else None

    async def upsert_material(
        self,
        material: FrameMaterialInDB,
        overwrite: bool = False,
    ) -> FrameMaterialInDB:
        """Idempotently insert or update a material record by code."""
        doc = material.model_dump(by_alias=True)
        doc["_id"] = ObjectId(material.id)

        if overwrite:
            await self.materials_col.update_one(
                {"code": material.code},
                {"$set": doc},
                upsert=True,
            )
        else:
            await self.materials_col.update_one(
                {"code": material.code},
                {"$setOnInsert": doc},
                upsert=True,
            )

        existing = await self.get_material_by_code(material.code)
        return existing or material

    # ---------------- Frame Moldings ----------------

    async def list_moldings(
        self,
        material_id: str | None = None,
        color: str | None = None,
        min_width: float | None = None,
        max_width: float | None = None,
        active_only: bool = True,
    ) -> list[FrameMoldingInDB]:
        """Query frame moldings with optional material, color, and width filters."""
        query: dict[str, Any] = {}
        if active_only:
            query["is_active"] = True

        if material_id:
            if ObjectId.is_valid(material_id):
                query["material_id"] = ObjectId(material_id)
            else:
                # Invalid ObjectId returns empty list safely
                return []

        if color:
            escaped_color = re.escape(color.strip())
            query["available_colors.name"] = {"$regex": escaped_color, "$options": "i"}

        if min_width is not None or max_width is not None:
            width_filter: dict[str, float] = {}
            if min_width is not None:
                width_filter["$gte"] = min_width
            if max_width is not None:
                width_filter["$lte"] = max_width
            query["profile_width_inches"] = width_filter

        cursor = self.moldings_col.find(query).sort("name", ASCENDING)
        items: list[FrameMoldingInDB] = []
        async for doc in cursor:
            items.append(FrameMoldingInDB(**doc))
        return items

    async def get_molding_by_id(self, molding_id: str) -> FrameMoldingInDB | None:
        """Find frame molding profile by string ObjectId."""
        if not ObjectId.is_valid(molding_id):
            return None
        doc = await self.moldings_col.find_one({"_id": ObjectId(molding_id)})
        return FrameMoldingInDB(**doc) if doc else None

    async def get_molding_by_sku(self, sku: str) -> FrameMoldingInDB | None:
        """Find frame molding profile by unique SKU."""
        doc = await self.moldings_col.find_one({"sku": sku.strip()})
        return FrameMoldingInDB(**doc) if doc else None

    async def upsert_molding(
        self,
        molding: FrameMoldingInDB,
        overwrite: bool = False,
    ) -> FrameMoldingInDB:
        """Idempotently insert or update a molding profile record by SKU."""
        doc = molding.model_dump(by_alias=True)
        doc["_id"] = ObjectId(molding.id)
        if ObjectId.is_valid(str(doc["material_id"])):
            doc["material_id"] = ObjectId(str(doc["material_id"]))

        if overwrite:
            await self.moldings_col.update_one(
                {"sku": molding.sku},
                {"$set": doc},
                upsert=True,
            )
        else:
            await self.moldings_col.update_one(
                {"sku": molding.sku},
                {"$setOnInsert": doc},
                upsert=True,
            )

        existing = await self.get_molding_by_sku(molding.sku)
        return existing or molding
