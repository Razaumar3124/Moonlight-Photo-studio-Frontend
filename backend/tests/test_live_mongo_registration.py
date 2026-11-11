"""Live integration tests for SAF Studio Registration against a running MongoDB instance.

Verifies end-to-end user document persistence, Argon2id hashing, and unique index enforcement.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient

from app.core.config import Settings, get_settings
from app.core.security import verify_password
from app.db.mongodb import mongo_manager
from app.main import create_application
from app.repositories.user_repository import UserRepository


async def _check_mongo_available() -> bool:
    try:
        client = AsyncMongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=1000)
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

    test_db_name = "saf_studio_pytest_live"
    settings = Settings(
        APP_NAME="SAF Studio Live Test",
        ENVIRONMENT="development",
        DEBUG=True,
        MONGODB_URL="mongodb://localhost:27017",
        DATABASE_NAME=test_db_name,
        MONGODB_TIMEOUT_MS=3000,
        CORS_ORIGINS=["http://localhost:5173"],
        SECRET_KEY="live-test-secret-key-min-32-chars-saf-studio-verification",
    )

    await mongo_manager.connect(settings)
    db = mongo_manager.get_database()

    # Clean up test collection
    await db["users"].delete_many({"email": {"$regex": "@live-test\\.safstudio\\.com$"}})
    await db["refresh_tokens"].delete_many({})

    user_repo = UserRepository(db)
    await user_repo.create_indexes()

    app = create_application()
    app.dependency_overrides[get_settings] = lambda: settings

    test_email = "live.user@live-test.safstudio.com"
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

        # Verify MongoDB document
        doc = await db["users"].find_one({"email": test_email})
        assert doc is not None
        assert doc["email"] == test_email
        assert doc["phone"] == test_phone
        assert doc["password_hash"].startswith("$argon2id$")
        assert verify_password(test_password, doc["password_hash"]) is True

        # Verify duplicate conflict (409)
        res_dup = await client.post("/api/v1/auth/register", json=payload)
        assert res_dup.status_code == 409
        assert res_dup.json()["error"]["code"] == "ACCOUNT_ALREADY_EXISTS"

    # Cleanup
    await db["users"].delete_many({"email": {"$regex": "@live-test\\.safstudio\\.com$"}})
    await mongo_manager.disconnect()
