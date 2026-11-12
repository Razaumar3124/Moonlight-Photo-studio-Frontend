"""Fixed-window rate limiting with a shared, bounded counter store.

``rate_limiter.hit(scope, subject, limit, window)`` counts one attempt and raises
``RateLimitExceededException`` (HTTP 429 + ``Retry-After``) once ``limit`` is exceeded.

Backends (``RATE_LIMIT_BACKEND``):

* ``mongodb`` – one atomic ``find_one_and_update`` upsert per hit on the ``rate_limits``
  collection, so every worker and instance shares the counters. A TTL index on
  ``expires_at`` keeps the collection bounded.
* ``memory`` – per-process dictionary capped at ``MAX_MEMORY_KEYS`` (expired windows are
  purged first, then the soonest-expiring keys are evicted). Used by tests, and as a fallback
  while MongoDB isn't connected.

Subjects (emails, phone numbers, IPs) are stored as SHA-256 digests, never in clear.
"""

import hashlib
import logging
import math
import time
from datetime import UTC, datetime, timedelta

from pymongo import ASCENDING, IndexModel, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.config import get_settings
from app.core.exceptions import DatabaseUnavailableException, RateLimitExceededException

logger = logging.getLogger("moonlight_studio.rate_limiter")

RATE_LIMIT_COLLECTION = "rate_limits"
MAX_MEMORY_KEYS = 50_000


def _storage_key(scope: str, subject: str) -> str:
    digest = hashlib.sha256(subject.strip().lower().encode("utf-8")).hexdigest()[:40]
    return f"{scope}:{digest}"


class MemoryRateLimitStore:
    """Bounded per-process fixed-window counters.

    Methods never await while mutating state, so each call is atomic on the event loop.
    """

    def __init__(self, max_keys: int = MAX_MEMORY_KEYS) -> None:
        self._max_keys = max_keys
        self._windows: dict[str, tuple[int, float]] = {}  # key -> (count, expires_at)

    def __len__(self) -> int:
        return len(self._windows)

    def _make_room(self, now: float) -> None:
        if len(self._windows) < self._max_keys:
            return
        for key in [k for k, (_, exp) in self._windows.items() if exp <= now]:
            del self._windows[key]
        if len(self._windows) >= self._max_keys:
            # Evict the soonest-expiring 10%: they carry the least remaining protection.
            evict = sorted(self._windows, key=lambda k: self._windows[k][1])
            for key in evict[: max(1, self._max_keys // 10)]:
                del self._windows[key]

    async def hit(self, key: str, window_seconds: int) -> tuple[int, float]:
        now = time.time()
        count, expires_at = self._windows.get(key, (0, 0.0))
        if expires_at <= now:
            if key not in self._windows:
                self._make_room(now)
            count, expires_at = 0, now + window_seconds
        count += 1
        self._windows[key] = (count, expires_at)
        return count, expires_at

    async def reset(self, key: str) -> None:
        self._windows.pop(key, None)

    def clear(self) -> None:
        self._windows.clear()


class MongoRateLimitStore:
    """Shared fixed-window counters in MongoDB (atomic per hit)."""

    def __init__(self, db: AsyncDatabase) -> None:
        self._collection = db[RATE_LIMIT_COLLECTION]

    async def hit(self, key: str, window_seconds: int) -> tuple[int, float]:
        now = datetime.now(UTC)
        new_expiry = now + timedelta(seconds=window_seconds)
        window_open = {"$gt": ["$expires_at", now]}
        pipeline = [
            {
                "$set": {
                    "count": {"$cond": [window_open, {"$add": ["$count", 1]}, 1]},
                    "expires_at": {"$cond": [window_open, "$expires_at", new_expiry]},
                }
            }
        ]
        for attempt in range(2):
            try:
                doc = await self._collection.find_one_and_update(
                    {"_id": key},
                    pipeline,
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                )
                break
            except DuplicateKeyError:
                # Two first-hits raced on the upsert; the retry updates the winner's document.
                if attempt:
                    raise DatabaseUnavailableException(issue="rate limit upsert conflict") from None
            except PyMongoError as exc:
                # Fail closed with the standard 503 (not an unhandled 500).
                raise DatabaseUnavailableException(
                    issue=f"rate limit store: {type(exc).__name__}"
                ) from exc
        expires_at: datetime = doc["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return int(doc["count"]), expires_at.timestamp()

    async def reset(self, key: str) -> None:
        try:
            await self._collection.delete_one({"_id": key})
        except PyMongoError as exc:
            raise DatabaseUnavailableException(
                issue=f"rate limit store: {type(exc).__name__}"
            ) from exc


async def ensure_rate_limit_indexes(db: AsyncDatabase) -> None:
    """TTL index: MongoDB deletes each counter once its window has closed."""
    await db[RATE_LIMIT_COLLECTION].create_indexes(
        [IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_expires_at")]
    )


class RateLimiter:
    """Facade that picks the configured backend for every call."""

    def __init__(self) -> None:
        self.memory = MemoryRateLimitStore()
        self._warned_fallback = False

    def _store(self) -> MemoryRateLimitStore | MongoRateLimitStore:
        if get_settings().RATE_LIMIT_BACKEND == "mongodb":
            from app.db.mongodb import mongo_manager

            if mongo_manager.db is not None:
                return MongoRateLimitStore(mongo_manager.db)
            if not self._warned_fallback:
                logger.warning("MongoDB not connected: rate limits fall back to process memory")
                self._warned_fallback = True
        return self.memory

    async def hit(
        self,
        scope: str,
        subject: str,
        limit: int,
        window_seconds: int,
        message: str | None = None,
    ) -> None:
        """Count one attempt for ``scope``/``subject``; raise 429 once over ``limit``."""
        count, expires_at = await self._store().hit(_storage_key(scope, subject), window_seconds)
        if count > limit:
            retry_after = max(1, math.ceil(expires_at - time.time()))
            logger.info("Rate limit exceeded: scope=%s count=%d limit=%d", scope, count, limit)
            if message:
                raise RateLimitExceededException(message, retry_after_seconds=retry_after)
            raise RateLimitExceededException(retry_after_seconds=retry_after)

    async def reset(self, scope: str, subject: str) -> None:
        await self._store().reset(_storage_key(scope, subject))

    def clear_all(self) -> None:
        """Clear in-process counters (test tear-down)."""
        self.memory.clear()


rate_limiter = RateLimiter()
