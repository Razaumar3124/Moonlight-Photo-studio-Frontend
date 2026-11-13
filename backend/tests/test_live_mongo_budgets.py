"""Live MongoDB checks for the usage budgets (skipped without a local MongoDB).

Uses only the throwaway ``moonlight_studio_pytest_live_budgets`` database on localhost, dropped
before and after. Proves the atomic guarantees that the in-memory store can't: concurrent
reservations from many tasks never exceed the ceiling, releases clamp at zero, the maintenance
lease is exclusive, and the TTL index exists.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pymongo import AsyncMongoClient

from app.services.usage_budget import (
    USAGE_COLLECTION,
    MongoUsageStore,
    ensure_usage_indexes,
)

LOCAL_MONGO_URL = "mongodb://localhost:27017"
TEST_DB_NAME = "moonlight_studio_pytest_live_budgets"


@pytest.fixture
async def live_db():
    client = AsyncMongoClient(LOCAL_MONGO_URL, serverSelectionTimeoutMS=1000)
    try:
        await client.admin.command("ping")
    except Exception:
        await client.close()
        pytest.skip("Local MongoDB instance not reachable on port 27017")
    await client.drop_database(TEST_DB_NAME)
    try:
        yield client[TEST_DB_NAME]
    finally:
        await client.drop_database(TEST_DB_NAME)
        await client.close()


async def test_concurrent_reservations_never_exceed_the_limit(live_db):
    store = MongoUsageStore(live_db)
    results = await asyncio.gather(*(store.reserve("email:t", 1, 100) for _ in range(300)))
    assert sum(1 for ok, _ in results if ok) == 100
    assert await store.get("email:t") == 100
    assert await live_db[USAGE_COLLECTION].count_documents({"_id": "email:t"}) == 1


async def test_boundary_and_oversized_reservations(live_db):
    store = MongoUsageStore(live_db)
    assert (await store.reserve("bytes", 600, 1000))[0] is True
    assert (await store.reserve("bytes", 401, 1000))[0] is False
    assert (await store.reserve("bytes", 400, 1000))[0] is True
    assert (await store.reserve("bytes", 1, 1000))[0] is False
    assert (await store.reserve("other", 1001, 1000))[0] is False  # never inserted
    assert await store.get("other") == 0
    assert await store.get("bytes") == 1000


async def test_release_clamps_at_zero_and_restores_room(live_db):
    store = MongoUsageStore(live_db)
    await store.reserve("k", 10, 100)
    await store.release("k", 4)
    assert await store.get("k") == 6
    await store.release("k", 50)
    assert await store.get("k") == 0
    await store.release("missing", 5)  # no error, no document
    assert await store.get("missing") == 0


async def test_concurrent_reserve_and_release_stay_consistent(live_db):
    store = MongoUsageStore(live_db)
    await asyncio.gather(*(store.reserve("c", 5, 10_000) for _ in range(100)))
    await asyncio.gather(*(store.release("c", 5) for _ in range(40)))
    assert await store.get("c") == 300


async def test_compare_and_set_only_applies_when_unchanged(live_db):
    store = MongoUsageStore(live_db)
    await store.reserve("r2", 500, 10_000)
    assert await store.compare_and_set("r2", 500, 700) is True
    assert await store.get("r2") == 700
    assert await store.compare_and_set("r2", 500, 1) is False  # stale expectation
    assert await store.get("r2") == 700
    assert await store.compare_and_set("fresh", 0, 42) is True  # first measurement
    assert await store.get("fresh") == 42
    await store.reserve("zero", 1, 10)
    await store.release("zero", 1)
    assert await store.compare_and_set("zero", 0, 9) is True


async def test_maintenance_lease_is_exclusive(live_db):
    store = MongoUsageStore(live_db)
    results = await asyncio.gather(*(store.acquire_lease("lease:x", 60) for _ in range(20)))
    assert sum(results) == 1
    assert await store.acquire_lease("lease:x", 60) is False
    # an expired lease can be taken again
    await live_db[USAGE_COLLECTION].update_one(
        {"_id": "lease:x"}, {"$set": {"lease_until": datetime.now(UTC) - timedelta(seconds=1)}}
    )
    assert await store.acquire_lease("lease:x", 60) is True


async def test_daily_counters_expire_through_a_ttl_index(live_db):
    await ensure_usage_indexes(live_db)
    index = await live_db[USAGE_COLLECTION].index_information()
    assert index["ttl_expires_at"]["expireAfterSeconds"] == 0
    store = MongoUsageStore(live_db)
    expires = datetime.now(UTC) + timedelta(days=3)
    await store.reserve("email:2026-01-01", 1, 100, expires)
    doc = await live_db[USAGE_COLLECTION].find_one({"_id": "email:2026-01-01"})
    assert abs(doc["expires_at"].replace(tzinfo=UTC) - expires) < timedelta(seconds=1)
    # permanent counters (stored bytes) carry no expiry
    await store.reserve("r2_bytes", 5, 100)
    assert "expires_at" not in await live_db[USAGE_COLLECTION].find_one({"_id": "r2_bytes"})
