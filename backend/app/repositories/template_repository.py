from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, IndexModel
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from app.models.template import LayoutTemplateInDB


class TemplateRepository:
    """Data access repository for layout_templates collection."""

    def __init__(self, db: AsyncDatabase) -> None:
        self.collection: AsyncCollection = db["layout_templates"]

    async def create_indexes(self) -> None:
        """Create necessary indexes for layout_templates collection idempotently."""
        indexes = [
            IndexModel([("slug", ASCENDING)], unique=True, name="idx_templates_slug"),
            IndexModel(
                [("category", ASCENDING), ("slots_count", ASCENDING)],
                name="idx_templates_category",
            ),
        ]
        await self.collection.create_indexes(indexes)

    async def list_templates(
        self,
        category: str | None = None,
        min_frames: int | None = None,
        max_frames: int | None = None,
        active_only: bool = True,
    ) -> list[LayoutTemplateInDB]:
        """Query gallery wall templates with optional category and frame-count bounds."""
        query: dict[str, Any] = {}
        if active_only:
            query["is_active"] = True

        if category:
            cat_norm = category.lower().strip()
            # Normalize centre vs focal_center for frontend-backend compatibility
            if cat_norm in ("centre", "focal_center"):
                query["category"] = {"$in": ["centre", "focal_center"]}
            else:
                query["category"] = cat_norm

        if min_frames is not None or max_frames is not None:
            frames_filter: dict[str, int] = {}
            if min_frames is not None:
                frames_filter["$gte"] = min_frames
            if max_frames is not None:
                frames_filter["$lte"] = max_frames
            query["slots_count"] = frames_filter

        cursor = self.collection.find(query).sort([("slots_count", ASCENDING), ("name", ASCENDING)])
        items: list[LayoutTemplateInDB] = []
        async for doc in cursor:
            items.append(LayoutTemplateInDB(**doc))
        return items

    async def get_template_by_id(self, template_id: str) -> LayoutTemplateInDB | None:
        """Find layout template by string ObjectId."""
        if not ObjectId.is_valid(template_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(template_id)})
        return LayoutTemplateInDB(**doc) if doc else None

    async def get_template_by_slug(self, slug: str) -> LayoutTemplateInDB | None:
        """Find layout template by unique slug."""
        doc = await self.collection.find_one({"slug": slug.strip()})
        return LayoutTemplateInDB(**doc) if doc else None

    async def upsert_template(
        self,
        template: LayoutTemplateInDB,
        overwrite: bool = False,
    ) -> LayoutTemplateInDB:
        """Idempotently insert or update a template record by slug."""
        doc = template.model_dump(by_alias=True)
        doc["_id"] = ObjectId(template.id)

        if overwrite:
            await self.collection.update_one(
                {"slug": template.slug},
                {"$set": doc},
                upsert=True,
            )
        else:
            await self.collection.update_one(
                {"slug": template.slug},
                {"$setOnInsert": doc},
                upsert=True,
            )

        existing = await self.get_template_by_slug(template.slug)
        return existing or template
