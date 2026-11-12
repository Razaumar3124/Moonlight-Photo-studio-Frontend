"""Live MongoDB checks for the Phase 2 concurrency guarantees (skipped without local MongoDB).

Uses only the throwaway ``moonlight_studio_pytest_live_security`` database on localhost,
dropped before and after.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pymongo import AsyncMongoClient

from app.core.security import hash_token
from app.models.session import RefreshTokenInDB
from app.repositories.session_repository import SessionRepository
from app.services.rate_limiter import (
    RATE_LIMIT_COLLECTION,
    MongoRateLimitStore,
    ensure_rate_limit_indexes,
)

LOCAL_MONGO_URL = "mongodb://localhost:27017"
TEST_DB_NAME = "moonlight_studio_pytest_live_security"


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


async def test_mongo_rate_limit_is_atomic_under_concurrency(live_db):
    await ensure_rate_limit_indexes(live_db)
    store = MongoRateLimitStore(live_db)

    counts = await asyncio.gather(*(store.hit("login:ip:abc", 60) for _ in range(40)))
    assert sorted(c for c, _ in counts) == list(range(1, 41))  # no lost or duplicate increments
    assert await live_db[RATE_LIMIT_COLLECTION].count_documents({}) == 1


async def test_mongo_rate_limit_window_resets_and_has_ttl(live_db):
    await ensure_rate_limit_indexes(live_db)
    store = MongoRateLimitStore(live_db)

    assert (await store.hit("otp:x", 1))[0] == 1
    assert (await store.hit("otp:x", 1))[0] == 2
    await asyncio.sleep(1.1)
    assert (await store.hit("otp:x", 1))[0] == 1  # new window

    indexes = await (await live_db[RATE_LIMIT_COLLECTION].list_indexes()).to_list()
    ttl = next(ix for ix in indexes if ix["name"] == "ttl_expires_at")
    assert ttl["expireAfterSeconds"] == 0


async def test_refresh_claim_has_exactly_one_winner(live_db):
    repo = SessionRepository(live_db)
    await repo.create_indexes()
    now = datetime.now(UTC)
    token_hash = hash_token("live-concurrency-token")
    await repo.create_refresh_token(
        RefreshTokenInDB(
            _id=str(ObjectId()),
            user_id=str(ObjectId()),
            token_hash=token_hash,
            family_id="family-live",
            expires_at=now + timedelta(days=1),
            created_at=now,
        )
    )

    claims = await asyncio.gather(
        *(repo.claim_refresh_token(token_hash, datetime.now(UTC)) for _ in range(20))
    )
    assert sum(c is not None for c in claims) == 1

    stored = await repo.get_refresh_token_by_hash(token_hash)
    assert stored.is_revoked is True
    assert stored.revoked_reason == "rotated" and stored.revoked_at is not None


async def test_expired_refresh_token_cannot_be_claimed(live_db):
    repo = SessionRepository(live_db)
    now = datetime.now(UTC)
    token_hash = hash_token("live-expired-token")
    await repo.create_refresh_token(
        RefreshTokenInDB(
            _id=str(ObjectId()),
            user_id=str(ObjectId()),
            token_hash=token_hash,
            family_id="family-expired",
            expires_at=now - timedelta(seconds=1),
            created_at=now - timedelta(days=1),
        )
    )
    assert await repo.claim_refresh_token(token_hash, now) is None


async def test_unreachable_rate_limit_store_fails_closed_with_503():
    """A down database must answer 503 DATABASE_UNAVAILABLE, never an unhandled 500."""
    from app.core.exceptions import DatabaseUnavailableException

    client = AsyncMongoClient("mongodb://127.0.0.1:1", serverSelectionTimeoutMS=200)
    try:
        store = MongoRateLimitStore(client["unreachable"])
        with pytest.raises(DatabaseUnavailableException):
            await store.hit("login:ip:x", 60)
    finally:
        await client.close()
