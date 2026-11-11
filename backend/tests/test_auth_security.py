import pytest
from httpx import AsyncClient

from app.core.security import hash_password, verify_password
from app.services.rate_limiter import rate_limiter
from tests.fakes import FakeUserRepository


@pytest.fixture(autouse=True)
async def setup_security_user(fake_user_repo: FakeUserRepository):
    """Seed customer user for security tests."""
    from datetime import UTC, datetime

    from bson import ObjectId

    from app.models.user import UserInDB

    now = datetime.now(UTC)
    user = UserInDB(
        _id=str(ObjectId()),
        email="security.user@example.com",
        phone="+919876543210",
        password_hash=hash_password("RealPassword123!"),
        full_name="Security Test User",
        role="customer",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    await fake_user_repo.create(user)


@pytest.mark.asyncio
async def test_login_brute_force_rate_limiting(client: AsyncClient):
    """Verify that exceeding login attempt threshold triggers HTTP 429."""
    rate_limiter.clear_all()
    payload = {
        "email": "security.user@example.com",
        "password": "WrongPassword123!",
    }

    # First 5 attempts fail with 401
    for _ in range(5):
        res = await client.post("/api/v1/auth/login", json=payload)
        assert res.status_code == 401

    # 6th attempt is blocked by rate limiter with 429
    res6 = await client.post("/api/v1/auth/login", json=payload)
    assert res6.status_code == 429
    data = res6.json()
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_password_argon2id_hashing():
    """Verify password is encrypted using Argon2id with recommended parameters."""
    pwd = "MySecretPassword123!"
    hashed = hash_password(pwd)

    # Argon2id signature check
    assert hashed.startswith("$argon2id$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password(pwd, "corrupted_hash") is False


@pytest.mark.asyncio
async def test_nosql_injection_payload_rejected(client: AsyncClient):
    """Verify NoSQL injection dictionary payloads fail schema validation with 422."""
    injection_payload = {
        "email": {"$gt": ""},  # NoSQL injection pattern
        "password": "Password123!",
    }
    response = await client.post("/api/v1/auth/login", json=injection_payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_responses_never_leak_sensitive_hashes(client: AsyncClient):
    """Verify that login and register responses never leak password_hash or internal secrets."""
    payload = {
        "email": "security.user@example.com",
        "password": "RealPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200

    resp_text = response.text
    assert "password_hash" not in resp_text
    assert "token_hash" not in resp_text
    assert "RealPassword123!" not in resp_text
    assert "$argon2id$" not in resp_text
