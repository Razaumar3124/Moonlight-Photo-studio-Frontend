"""MongoDB asynchronous persistence repository for quotation requests and shareable reports."""

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from app.models.quote import QuoteInDB

logger = logging.getLogger("saf_studio.quote_repository")


class QuoteRepository:
    """Repository handling CRUD operations and atomic sequence generation for quotes."""

    def __init__(self, db: AsyncDatabase) -> None:
        self.db = db
        self.collection: AsyncCollection = db["quotes"]
        self.counters: AsyncCollection = db["counters"]

    async def create_indexes(self) -> None:
        """Create necessary indexes for performance, uniqueness, and expiration."""
        try:
            # 1. Unique index on human-readable quote reference (SQ-YYYY-XXXX)
            await self.collection.create_index(
                [("quote_reference", ASCENDING)],
                unique=True,
                name="idx_quotes_reference_unique",
            )
            # 2. Compound index for customer quote listing
            await self.collection.create_index(
                [("user_id", ASCENDING), ("created_at", DESCENDING)],
                name="idx_quotes_user_created",
            )
            # 3. Fast lookup index on hashed share tokens
            await self.collection.create_index(
                [("share_token_hash", ASCENDING)],
                name="idx_quotes_share_token_hash",
            )
            # 4. Status filter index
            await self.collection.create_index(
                [("status", ASCENDING)],
                name="idx_quotes_status",
            )
            # 5. MongoDB TTL index for automated expiry cleanup
            await self.collection.create_index(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                name="idx_quotes_ttl_expiry",
            )
            logger.info("MongoDB 'quotes' indexes created successfully")
        except Exception as exc:
            logger.warning("Could not complete quotes index creation: %s", exc)

    async def get_next_quote_reference(self) -> str:
        """Atomically generate the next sequential quote reference code (SQ-YYYY-XXXX)."""
        current_year = datetime.now(UTC).year
        counter_id = f"quote_ref_{current_year}"

        doc = await self.counters.find_one_and_update(
            {"_id": counter_id},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        seq = doc.get("seq", 1) if doc else 1
        return f"SQ-{current_year}-{seq:04d}"

    async def create(self, quote: QuoteInDB) -> QuoteInDB:
        """Insert a newly prepared quote document into MongoDB."""
        doc = quote.model_dump(by_alias=True)
        doc["_id"] = str(quote.id)
        doc["user_id"] = str(quote.user_id)
        await self.collection.insert_one(doc)
        return quote

    async def get_by_id(self, quote_id: str) -> QuoteInDB | None:
        """Retrieve quote by MongoDB ObjectId or quote_reference."""
        query: dict[str, Any]
        if ObjectId.is_valid(quote_id):
            query = {"$or": [{"_id": str(quote_id)}, {"quote_reference": quote_id}]}
        else:
            query = {"quote_reference": quote_id}

        doc = await self.collection.find_one(query)
        if not doc:
            return None
        return QuoteInDB(**doc)

    async def get_by_reference(self, reference: str) -> QuoteInDB | None:
        """Retrieve quote by exact sequential quote reference."""
        doc = await self.collection.find_one({"quote_reference": reference})
        if not doc:
            return None
        return QuoteInDB(**doc)

    async def get_by_share_token_hash(self, token_hash: str) -> QuoteInDB | None:
        """Retrieve quote by the SHA-256 hash of its share token."""
        doc = await self.collection.find_one({"share_token_hash": token_hash})
        if not doc:
            return None
        return QuoteInDB(**doc)

    async def get_by_user_id(self, user_id: str, skip: int = 0, limit: int = 20) -> list[QuoteInDB]:
        """List quotes owned by a user sorted newest first."""
        cursor = (
            self.collection.find({"user_id": str(user_id)})
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [QuoteInDB(**d) for d in docs]

    async def delete(self, quote_id: str) -> bool:
        """Delete quote document."""
        res = await self.collection.delete_one({"_id": str(quote_id)})
        return res.deleted_count > 0
