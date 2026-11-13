"""Housekeeping that keeps stored data, and the storage budget, honest.

One run (guarded by a MongoDB lease so only one worker does it per interval):

1. **Retry deletions** that storage refused earlier (photos deleted by users whose objects
   were still pending removal) and free their bytes.
2. **Sweep expired quote previews**: preview images under ``quotes/`` are deleted once their
   quote expired (``QUOTE_SHARE_EXPIRY_DAYS`` + a grace day). A preview is never deleted while a
   not-yet-expired quote references it, and nothing outside ``quotes/`` (customer photos) is
   touched here.
3. **Reconcile** the byte counter with what storage really holds. The counter is only replaced
   when it did not change during the measurement (compare-and-set), so a concurrent upload can
   never be lost; if it did change, the next run measures again.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.core import limits
from app.repositories.photo_repository import PhotoRepository
from app.repositories.quote_repository import QuoteRepository
from app.services.photo_service import PhotoService
from app.services.usage_budget import LEASE_KEY, usage_budget
from app.storage import ObjectStorage

logger = logging.getLogger("moonlight_studio.maintenance")

QUOTE_PREFIX = "quotes/"
DELETE_BATCH = 500


class StorageMaintenance:
    def __init__(
        self,
        storage: ObjectStorage,
        photo_repo: PhotoRepository,
        quote_repo: QuoteRepository,
        photo_service: PhotoService,
    ) -> None:
        self.storage = storage
        self.photo_repo = photo_repo
        self.quote_repo = quote_repo
        self.photo_service = photo_service

    async def retry_pending_photo_deletes(self) -> int:
        """Remove objects of deleted photos that storage could not delete earlier."""
        photos = await self.photo_repo.list_purge_pending(limit=100)
        for photo in photos:
            await self.photo_service.purge_objects(photo.id, photo.purge_pending, was_pending=True)
        return len(photos)

    async def sweep_expired_quote_previews(self, now: datetime | None = None) -> int:
        """Delete preview images of quotes that expired; returns how many were removed."""
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(
            days=limits.QUOTE_SHARE_EXPIRY_DAYS + limits.QUOTE_PREVIEW_GRACE_DAYS
        )
        expired = []
        for obj in await self.storage.list_objects(QUOTE_PREFIX):
            modified = obj.last_modified
            if modified.tzinfo is None:
                modified = modified.replace(tzinfo=UTC)
            if modified >= cutoff:
                continue
            if await self.quote_repo.has_active_quote_for_preview(obj.key):
                continue  # still referenced by a live quote: keep
            expired.append(obj)

        removed = 0
        for start in range(0, len(expired), DELETE_BATCH):
            batch = expired[start : start + DELETE_BATCH]
            gone = set(await self.storage.delete_objects([o.key for o in batch]))
            await usage_budget.release_storage(sum(o.size for o in batch if o.key in gone))
            removed += len(gone)
        if removed:
            logger.info("Removed %d expired quote preview(s)", removed)
        return removed

    async def reconcile_counter(self, attempts: int = 3) -> bool:
        """Align the stored-bytes counter with the real size of the bucket."""
        for _ in range(attempts):
            before = await usage_budget.storage_used()
            actual = sum(o.size for o in await self.storage.list_objects(""))
            if await usage_budget.reconcile_storage(before, actual):
                if actual != before:
                    logger.warning("Storage counter corrected: %d -> %d bytes", before, actual)
                return True
        logger.info("Storage counter changed during measurement; will retry next run")
        return False

    async def run_once(self) -> dict:
        if not await usage_budget.store().acquire_lease(
            LEASE_KEY, limits.MAINTENANCE_INTERVAL_SECONDS - 60
        ):
            return {"skipped": True}
        result: dict = {"skipped": False}
        for name, step in (
            ("photo_deletes_retried", self.retry_pending_photo_deletes),
            ("quote_previews_removed", self.sweep_expired_quote_previews),
            ("counter_reconciled", self.reconcile_counter),
        ):
            try:
                result[name] = await step()
            except Exception as exc:  # one failing step must not stop the others
                logger.error("Storage maintenance step %s failed: %s", name, exc)
                result[name] = None
        return result


async def maintenance_loop(maintenance: StorageMaintenance, first_delay: float = 60.0) -> None:
    """Run maintenance forever (cancelled on shutdown)."""
    await asyncio.sleep(first_delay)
    while True:
        try:
            await maintenance.run_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Storage maintenance failed: %s", exc)
        await asyncio.sleep(limits.MAINTENANCE_INTERVAL_SECONDS)
