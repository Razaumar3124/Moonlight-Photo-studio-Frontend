"""Live integration test for registration against a local MongoDB (skipped if none is running).

Verifies end-to-end user persistence, Argon2id hashing and unique-index enforcement.
Only ever touches the throwaway ``moonlight_studio_pytest_live`` database on localhost,
which is dropped afterwards.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient

from app.core.config import Settings, get_settings
from app.core.security import verify_password
from app.db.mongodb import mongo_manager
from app.main import create_application
from app.repositories.user_repository import UserRepository

LOCAL_MONGO_URL = "mongodb://localhost:27017"
TEST_DB_NAME = "moonlight_studio_pytest_live"


async def _check_mongo_available() -> bool:
    try:
        client = AsyncMongoClient(LOCAL_MONGO_URL, serverSelectionTimeoutMS=1000)
        await client.admin.command("ping")
        await client.close()
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_live_mongodb_registration_workflow():
    """Verify live registration writes directly to MongoDB and verifies Argon2id hash."""
    if not await _check_mongo_available():
        pytest.skip("Local MongoDB instance not reachable on port 27017")

    settings = Settings(
        APP_NAME="Moonlight Photo Studio Live Test",
        ENVIRONMENT="development",
        DEBUG=True,
        MONGODB_URL=LOCAL_MONGO_URL,
        DATABASE_NAME=TEST_DB_NAME,
        MONGODB_TIMEOUT_MS=3000,
        CORS_ORIGINS=["http://localhost:5173"],
        SECRET_KEY="live-test-secret-key-min-32-chars-moonlight-verification",
    )

    # Never let a stale global connection (e.g. to another database) be reused.
    await mongo_manager.disconnect()
    await mongo_manager.connect(settings)
    db = mongo_manager.get_database()
    assert db.name == TEST_DB_NAME

    try:
        await mongo_manager.client.drop_database(TEST_DB_NAME)
        user_repo = UserRepository(db)
        await user_repo.create_indexes()

        app = create_application()
        app.dependency_overrides[get_settings] = lambda: settings

        test_email = "live.user@live-test.example.com"
        test_phone = "+919876543288"
        test_password = "LiveSecurePassword123!"
        test_name = "Live Test Customer"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            payload = {
                "full_name": test_name,
                "email": test_email,
                "phone": test_phone,
                "password": test_password,
            }
            res = await client.post("/api/v1/auth/register", json=payload)
            assert res.status_code == 201

            data = res.json()
            assert data["user"]["email"] == test_email
            assert "password" not in data["user"]
            assert "password_hash" not in data["user"]
            assert "refresh_token" in res.cookies

            doc = await db["users"].find_one({"email": test_email})
            assert doc is not None
            assert doc["email"] == test_email
            assert doc["phone"] == test_phone
            assert doc["password_hash"].startswith("$argon2id$")
            assert verify_password(test_password, doc["password_hash"]) is True

            res_dup = await client.post("/api/v1/auth/register", json=payload)
            assert res_dup.status_code == 409
            assert res_dup.json()["error"]["code"] == "ACCOUNT_ALREADY_EXISTS"
    finally:
        await mongo_manager.client.drop_database(TEST_DB_NAME)
        await mongo_manager.disconnect()
