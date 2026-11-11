import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from app.models.design import DesignInDB
from app.models.design_version import DesignVersionInDB

logger = logging.getLogger("saf_studio.design_repo")


class DesignRepository:
    """Data access repository for 'designs' and 'design_versions' collections."""

    def __init__(self, db: AsyncDatabase) -> None:
        self.db: AsyncDatabase = db
        self.designs: AsyncCollection = db["designs"]
        self.versions: AsyncCollection = db["design_versions"]

    async def create_indexes(self) -> None:
        """Create necessary indexes for designs and design_versions idempotently."""
        design_indexes = [
            IndexModel(
                [
                    ("user_id", ASCENDING),
                    ("is_deleted", ASCENDING),
                    ("updated_at", DESCENDING),
                ],
                name="idx_designs_user",
            ),
            IndexModel(
                [
                    ("_id", ASCENDING),
                    ("user_id", ASCENDING),
                ],
                name="idx_designs_id_user",
            ),
        ]
        await self.designs.create_indexes(design_indexes)

        version_indexes = [
            IndexModel(
                [
                    ("design_id", ASCENDING),
                    ("version_number", ASCENDING),
                ],
                name="idx_design_versions_unique",
                unique=True,
            ),
            IndexModel(
                [
                    ("design_id", ASCENDING),
                    ("created_at", DESCENDING),
                ],
                name="idx_design_versions_created",
            ),
        ]
        await self.versions.create_indexes(version_indexes)
        logger.info("Design and design_versions collection indexes verified")

    async def create_design(self, design: DesignInDB) -> DesignInDB:
        """Insert a new gallery wall design into MongoDB."""
        doc = design.model_dump(by_alias=True)
        doc["_id"] = ObjectId(design.id)
        if ObjectId.is_valid(str(design.user_id)):
            doc["user_id"] = ObjectId(str(design.user_id))
        if design.current_version_id and ObjectId.is_valid(str(design.current_version_id)):
            doc["current_version_id"] = ObjectId(str(design.current_version_id))

        await self.designs.insert_one(doc)
        return design

    async def get_design_by_id(
        self,
        design_id: str,
        include_deleted: bool = False,
    ) -> DesignInDB | None:
        """Find design by string ObjectId."""
        if not ObjectId.is_valid(design_id):
            return None

        query: dict[str, Any] = {"_id": ObjectId(design_id)}
        if not include_deleted:
            query["is_deleted"] = False

        doc = await self.designs.find_one(query)
        if not doc:
            return None

        # Convert ObjectIds to strings
        doc["_id"] = str(doc["_id"])
        doc["user_id"] = str(doc["user_id"])
        if doc.get("current_version_id"):
            doc["current_version_id"] = str(doc["current_version_id"])

        return DesignInDB(**doc)

    async def update_design(
        self,
        design_id: str,
        updates: dict[str, Any],
    ) -> DesignInDB | None:
        """Apply partial updates to a design document."""
        if not ObjectId.is_valid(design_id):
            return None

        mongo_updates: dict[str, Any] = {}
        for key, value in updates.items():
            if key == "current_version_id" and value and ObjectId.is_valid(str(value)):
                mongo_updates[key] = ObjectId(str(value))
            elif key == "user_id" and value and ObjectId.is_valid(str(value)):
                mongo_updates[key] = ObjectId(str(value))
            else:
                mongo_updates[key] = value

        mongo_updates["updated_at"] = datetime.now(UTC)

        doc = await self.designs.find_one_and_update(
            {"_id": ObjectId(design_id), "is_deleted": False},
            {"$set": mongo_updates},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            return None

        doc["_id"] = str(doc["_id"])
        doc["user_id"] = str(doc["user_id"])
        if doc.get("current_version_id"):
            doc["current_version_id"] = str(doc["current_version_id"])

        return DesignInDB(**doc)

    async def delete_design(self, design_id: str) -> bool:
        """Soft-delete a design document."""
        if not ObjectId.is_valid(design_id):
            return False

        now = datetime.now(UTC)
        result = await self.designs.update_one(
            {"_id": ObjectId(design_id), "is_deleted": False},
            {"$set": {"is_deleted": True, "deleted_at": now, "updated_at": now}},
        )
        return result.modified_count > 0

    async def list_designs_by_user(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
        sort: str = "updated_at:desc",
    ) -> tuple[list[DesignInDB], int]:
        """List active designs owned by user with pagination and optional search/filter."""
        if not ObjectId.is_valid(user_id):
            return [], 0

        query: dict[str, Any] = {
            "user_id": ObjectId(user_id),
            "is_deleted": False,
        }

        if status:
            query["status"] = status

        if search:
            query["title"] = {"$regex": search.strip(), "$options": "i"}

        total = await self.designs.count_documents(query)
        if total == 0:
            return [], 0

        # Sort parsing
        sort_field, sort_dir = "updated_at", DESCENDING
        if sort:
            parts = sort.split(":")
            sort_field = parts[0]
            if len(parts) > 1 and parts[1].lower() == "asc":
                sort_dir = ASCENDING

        skip = (page - 1) * page_size
        cursor = self.designs.find(query).sort(sort_field, sort_dir).skip(skip).limit(page_size)

        items: list[DesignInDB] = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["user_id"] = str(doc["user_id"])
            if doc.get("current_version_id"):
                doc["current_version_id"] = str(doc["current_version_id"])
            items.append(DesignInDB(**doc))

        return items, total

    async def get_next_version_number(self, design_id: str) -> int:
        """Atomically increment and return the sequential version counter for a design."""
        if not ObjectId.is_valid(design_id):
            raise ValueError(f"Invalid design ObjectId: {design_id}")

        doc = await self.designs.find_one_and_update(
            {"_id": ObjectId(design_id), "is_deleted": False},
            {"$inc": {"version_counter": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise ValueError(f"Design '{design_id}' not found or deleted")

        return int(doc.get("version_counter", 1))

    async def create_version(self, version: DesignVersionInDB) -> DesignVersionInDB:
        """Insert an immutable design version snapshot into MongoDB."""
        doc = version.model_dump(by_alias=True)
        doc["_id"] = ObjectId(version.id)
        if ObjectId.is_valid(str(version.design_id)):
            doc["design_id"] = ObjectId(str(version.design_id))

        # Ensure photo_ids within items are converted if valid
        for item in doc.get("items", []):
            if item.get("photo_id") and ObjectId.is_valid(str(item["photo_id"])):
                item["photo_id"] = ObjectId(str(item["photo_id"]))

        await self.versions.insert_one(doc)
        return version

    async def get_version_by_id(self, version_id: str) -> DesignVersionInDB | None:
        """Retrieve a specific design version by ID."""
        if not ObjectId.is_valid(version_id):
            return None

        doc = await self.versions.find_one({"_id": ObjectId(version_id)})
        if not doc:
            return None

        doc["_id"] = str(doc["_id"])
        doc["design_id"] = str(doc["design_id"])
        for item in doc.get("items", []):
            if item.get("photo_id"):
                item["photo_id"] = str(item["photo_id"])

        return DesignVersionInDB(**doc)

    async def get_latest_version(self, design_id: str) -> DesignVersionInDB | None:
        """Retrieve the latest version snapshot for a design."""
        if not ObjectId.is_valid(design_id):
            return None

        doc = await self.versions.find_one(
            {"design_id": ObjectId(design_id)},
            sort=[("version_number", DESCENDING)],
        )
        if not doc:
            return None

        doc["_id"] = str(doc["_id"])
        doc["design_id"] = str(doc["design_id"])
        for item in doc.get("items", []):
            if item.get("photo_id"):
                item["photo_id"] = str(item["photo_id"])

        return DesignVersionInDB(**doc)

    async def list_versions_by_design(self, design_id: str) -> list[DesignVersionInDB]:
        """List all version snapshots for a design sorted by version_number descending."""
        if not ObjectId.is_valid(design_id):
            return []

        cursor = self.versions.find({"design_id": ObjectId(design_id)}).sort(
            "version_number", DESCENDING
        )

        results: list[DesignVersionInDB] = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["design_id"] = str(doc["design_id"])
            for item in doc.get("items", []):
                if item.get("photo_id"):
                    item["photo_id"] = str(item["photo_id"])
            results.append(DesignVersionInDB(**doc))

        return results
