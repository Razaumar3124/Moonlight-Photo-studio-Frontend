"""Shared, atomic usage budgets for free-tier resources (emails/day, stored bytes, AI requests).

A budget is a counter with a hard ceiling. ``reserve(key, amount, limit)`` adds ``amount`` *only if*
the total stays within ``limit`` and does so in one atomic MongoDB operation, so concurrent
requests and several workers can never over-allocate. ``release`` gives a reservation back when the
work did not happen (failed send, failed upload, deleted object).

Backends follow ``RATE_LIMIT_BACKEND`` like the rate limiter: ``mongodb`` in production (collection
``usage_counters``), per-process ``memory`` for tests and single-process development.

Daily counters carry an ``expires_at`` so a TTL index removes old days; permanent counters
(stored bytes) have none.
"""

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from pymongo import ASCENDING, IndexModel, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core import limits
from app.core.config import get_settings
from app.core.exceptions import DatabaseUnavailableException

logger = logging.getLogger("moonlight_studio.usage_budget")

USAGE_COLLECTION = "usage_counters"
STORAGE_KEY = "r2_bytes"
LEASE_KEY = "lease:storage_maintenance"


def utc_day(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m-%d")


def email_key(now: datetime | None = None) -> str:
    return f"email:{utc_day(now)}"


def groq_requests_key(now: datetime | None = None) -> str:
    return f"groq_requests:{utc_day(now)}"


def groq_tokens_key(now: datetime | None = None) -> str:
    return f"groq_tokens:{utc_day(now)}"


def register_ip_key(ip_digest: str, now: datetime | None = None) -> str:
    return f"register_ip:{utc_day(now)}:{ip_digest}"


def seconds_until_utc_midnight(now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    tomorrow = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - current).total_seconds()))


def _day_expiry(now: datetime | None = None) -> datetime:
    """Counters of a UTC day are kept two further days (for diagnostics), then TTL-deleted."""
    current = now or datetime.now(UTC)
    midnight = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(days=3)


class MemoryUsageStore:
    """Per-process counters. Methods never await mid-update, so each call is atomic."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._leases: dict[str, float] = {}

    async def reserve(
        self, key: str, amount: int, limit: int, expires_at: datetime | None = None
    ) -> tuple[bool, int]:
        current = self._counts.get(key, 0)
        if amount > limit or current + amount > limit:
            return False, current
        self._counts[key] = current + amount
        return True, current + amount

    async def release(self, key: str, amount: int) -> None:
        if key in self._counts:
            self._counts[key] = max(0, self._counts[key] - amount)

    async def get(self, key: str) -> int:
        return self._counts.get(key, 0)

    async def compare_and_set(self, key: str, expected: int, new: int) -> bool:
        if self._counts.get(key, 0) != expected:
            return False
        self._counts[key] = max(0, new)
        return True

    async def acquire_lease(self, key: str, seconds: int) -> bool:
        import time

        now = time.time()
        if self._leases.get(key, 0.0) > now:
            return False
        self._leases[key] = now + seconds
        return True

    def clear(self) -> None:
        self._counts.clear()
        self._leases.clear()


class MongoUsageStore:
    """Counters in MongoDB: every change is a single atomic update on one document."""

    def __init__(self, db: AsyncDatabase) -> None:
        self._collection = db[USAGE_COLLECTION]

    @staticmethod
    def _unavailable(exc: Exception) -> DatabaseUnavailableException:
        return DatabaseUnavailableException(issue=f"usage store: {type(exc).__name__}")

    async def reserve(
        self, key: str, amount: int, limit: int, expires_at: datetime | None = None
    ) -> tuple[bool, int]:
        if amount > limit:
            return False, await self.get(key)
        update: dict = {"$inc": {"count": amount}}
        if expires_at is not None:
            update["$setOnInsert"] = {"expires_at": expires_at}
        for _ in range(3):
            try:
                # The filter only matches while there is room. When it does not match, the
                # upsert would insert a second document with the same _id, which MongoDB
                # rejects: that duplicate-key error is the "over the limit" answer.
                doc = await self._collection.find_one_and_update(
                    {"_id": key, "count": {"$lte": limit - amount}},
                    update,
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                )
                return True, int(doc["count"])
            except DuplicateKeyError:
                current = await self.get(key)
                if current + amount > limit:
                    return False, current
                # Two first-ever reservations raced on the insert: the document exists now.
            except PyMongoError as exc:
                raise self._unavailable(exc) from exc
        return False, await self.get(key)

    async def release(self, key: str, amount: int) -> None:
        try:
            res = await self._collection.update_one(
                {"_id": key, "count": {"$gte": amount}}, {"$inc": {"count": -amount}}
            )
            if res.matched_count == 0:
                await self._collection.update_one(
                    {"_id": key, "count": {"$lt": amount}}, {"$set": {"count": 0}}
                )
        except PyMongoError as exc:
            raise self._unavailable(exc) from exc

    async def get(self, key: str) -> int:
        try:
            doc = await self._collection.find_one({"_id": key}, {"count": 1})
        except PyMongoError as exc:
            raise self._unavailable(exc) from exc
        return int(doc["count"]) if doc else 0

    async def compare_and_set(self, key: str, expected: int, new: int) -> bool:
        try:
            if expected == 0:
                try:
                    await self._collection.update_one(
                        {"_id": key, "$or": [{"count": 0}, {"count": {"$exists": False}}]},
                        {"$set": {"count": max(0, new)}},
                        upsert=True,
                    )
                    return True
                except DuplicateKeyError:
                    return False
            res = await self._collection.update_one(
                {"_id": key, "count": expected}, {"$set": {"count": max(0, new)}}
            )
            return res.matched_count == 1
        except PyMongoError as exc:
            raise self._unavailable(exc) from exc

    async def acquire_lease(self, key: str, seconds: int) -> bool:
        """At most one worker holds a named lease at a time (maintenance runs once per interval)."""
        now = datetime.now(UTC)
        try:
            await self._collection.update_one(
                {"_id": key, "$or": [{"lease_until": {"$lt": now}}, {"lease_until": None}]},
                {"$set": {"lease_until": now + timedelta(seconds=seconds)}},
                upsert=True,
            )
            return True
        except DuplicateKeyError:
            return False
        except PyMongoError as exc:
            raise self._unavailable(exc) from exc


async def ensure_usage_indexes(db: AsyncDatabase) -> None:
    await db[USAGE_COLLECTION].create_indexes(
        [IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_expires_at")]
    )


class UsageBudget:
    """Facade choosing the configured store, plus the named budgets the app uses."""

    def __init__(self) -> None:
        self.memory = MemoryUsageStore()

    def store(self) -> MemoryUsageStore | MongoUsageStore:
        if get_settings().RATE_LIMIT_BACKEND == "mongodb":
            from app.db.mongodb import mongo_manager

            if mongo_manager.db is not None:
                return MongoUsageStore(mongo_manager.db)
        return self.memory

    def clear_all(self) -> None:
        self.memory.clear()

    # -- Resend emails (per UTC day) -------------------------------------------------------

    async def reserve_email(self) -> bool:
        """Claim one email of today's allowance. False once the daily limit is used up."""
        ok, total = await self.store().reserve(
            email_key(), 1, limits.EMAIL_DAILY_LIMIT, _day_expiry()
        )
        if ok and total == limits.EMAIL_WARN_AT:
            logger.warning(
                "Email budget warning: %d of %d emails used today",
                total,
                limits.EMAIL_DAILY_LIMIT,
            )
        if not ok:
            logger.error(
                "Email daily limit (%d) reached; sending is blocked", limits.EMAIL_DAILY_LIMIT
            )
        return ok

    async def release_email(self) -> None:
        await self.store().release(email_key(), 1)

    async def email_exhausted(self) -> bool:
        return await self.store().get(email_key()) >= limits.EMAIL_DAILY_LIMIT

    async def email_usage(self) -> dict:
        used = await self.store().get(email_key())
        return {
            "day_utc": utc_day(),
            "used": used,
            "limit": limits.EMAIL_DAILY_LIMIT,
            "warn_at": limits.EMAIL_WARN_AT,
            "remaining": max(0, limits.EMAIL_DAILY_LIMIT - used),
            "status": (
                "exhausted"
                if used >= limits.EMAIL_DAILY_LIMIT
                else "warning"
                if used >= limits.EMAIL_WARN_AT
                else "ok"
            ),
        }

    # -- Object storage bytes (R2) ---------------------------------------------------------

    async def reserve_storage(self, size: int) -> bool:
        ok, total = await self.store().reserve(STORAGE_KEY, size, limits.R2_STORAGE_LIMIT_BYTES)
        if ok and total >= limits.R2_STORAGE_LIMIT_BYTES * limits.R2_STORAGE_WARN_FRACTION:
            logger.warning(
                "Storage budget warning: %d of %d bytes reserved",
                total,
                limits.R2_STORAGE_LIMIT_BYTES,
            )
        if not ok:
            logger.error(
                "Storage limit (%d bytes) reached; uploads are blocked",
                limits.R2_STORAGE_LIMIT_BYTES,
            )
        return ok

    async def release_storage(self, size: int) -> None:
        if size > 0:
            await self.store().release(STORAGE_KEY, size)

    async def storage_used(self) -> int:
        return await self.store().get(STORAGE_KEY)

    async def storage_usage(self) -> dict:
        used = await self.storage_used()
        limit = limits.R2_STORAGE_LIMIT_BYTES
        return {
            "used_bytes": used,
            "limit_bytes": limit,
            "percent": round(used * 100 / limit, 2),
            "status": (
                "exhausted"
                if used >= limit
                else "warning"
                if used >= limit * limits.R2_STORAGE_WARN_FRACTION
                else "ok"
            ),
        }

    async def reconcile_storage(self, expected_before: int, actual_bytes: int) -> bool:
        """Set the counter to the measured size, unless it changed meanwhile (then retry later)."""
        return await self.store().compare_and_set(STORAGE_KEY, expected_before, actual_bytes)

    # -- Groq (requests and tokens per UTC day, shared by every user and worker) ------------

    async def reserve_groq_request(self) -> bool:
        ok, _ = await self.store().reserve(
            groq_requests_key(), 1, limits.GROQ_DAILY_REQUEST_LIMIT, _day_expiry()
        )
        return ok

    async def groq_tokens_exhausted(self) -> bool:
        return await self.store().get(groq_tokens_key()) >= limits.GROQ_DAILY_TOKEN_BUDGET

    async def add_groq_tokens(self, tokens: int) -> None:
        if tokens > 0:
            # Tokens are only known after the call, so this may overshoot by one response.
            await self.store().reserve(
                groq_tokens_key(), tokens, limits.GROQ_DAILY_TOKEN_BUDGET + tokens, _day_expiry()
            )

    # -- Registrations per IP per day ------------------------------------------------------

    async def reserve_registration(self, ip: str | None) -> bool:
        """Claim one new-account slot for this IP today (IPs are stored only as digests)."""
        digest = hashlib.sha256((ip or "unknown").strip().lower().encode("utf-8")).hexdigest()[:32]
        ok, _ = await self.store().reserve(
            register_ip_key(digest), 1, limits.REGISTER_DAILY_PER_IP, _day_expiry()
        )
        return ok

    async def release_registration(self, ip: str | None) -> None:
        digest = hashlib.sha256((ip or "unknown").strip().lower().encode("utf-8")).hexdigest()[:32]
        await self.store().release(register_ip_key(digest), 1)


usage_budget = UsageBudget()
