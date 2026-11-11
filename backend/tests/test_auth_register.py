import asyncio

import pytest
from httpx import AsyncClient

from app.core.security import verify_password
from tests.fakes import FakeUserRepository


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful user registration returns 201 with User and Tokens."""
    payload = {
        "full_name": "Aarav Sharma",
        "email": "aarav.sharma@example.com",
        "phone": "+919876543210",
        "password": "SecurePassword123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "user" in data
    assert "tokens" in data

    # Check user attributes
    user = data["user"]
    assert user["email"] == "aarav.sharma@example.com"
    assert user["full_name"] == "Aarav Sharma"
    assert user["phone"] == "+919876543210"
    assert user["role"] == "customer"
    assert user["is_active"] is True
    assert "id" in user
    assert "created_at" in user
    assert "password_hash" not in user
    assert "password" not in user

    # Check tokens
    tokens = data["tokens"]
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 1800

    # Verify httpOnly refresh cookie was set
    cookies = response.cookies
    assert "refresh_token" in cookies
    assert cookies["refresh_token"] == tokens["refresh_token"]


@pytest.mark.asyncio
async def test_register_duplicate_email_conflict(client: AsyncClient):
    """Test registering with an existing email returns 409 with field error."""
    payload1 = {
        "full_name": "First User",
        "email": "duplicate@example.com",
        "phone": "+919876543210",
        "password": "Password123!",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload1)
    assert res1.status_code == 201

    # Attempt second registration with same email but different phone
    payload2 = {
        "full_name": "Second User",
        "email": "duplicate@example.com",
        "phone": "+919876543211",
        "password": "Password123!",
    }
    res2 = await client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 409

    data = res2.json()
    assert data["error"]["code"] == "ACCOUNT_ALREADY_EXISTS"
    assert data["error"]["details"][0]["field"] == "email"


@pytest.mark.asyncio
async def test_register_duplicate_phone_conflict(client: AsyncClient):
    """Test registering with an existing phone returns 409 with field error."""
    payload1 = {
        "full_name": "First User",
        "email": "user1@example.com",
        "phone": "+919876543210",
        "password": "Password123!",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload1)
    assert res1.status_code == 201

    payload2 = {
        "full_name": "Second User",
        "email": "user2@example.com",
        "phone": "+919876543210",
        "password": "Password123!",
    }
    res2 = await client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 409

    data = res2.json()
    assert data["error"]["code"] == "ACCOUNT_ALREADY_EXISTS"
    assert data["error"]["details"][0]["field"] == "phone"


@pytest.mark.asyncio
async def test_register_invalid_phone_format(client: AsyncClient):
    """Test registration with invalid mobile number returns 422 validation error."""
    payload = {
        "full_name": "Valid Name",
        "email": "valid@example.com",
        "phone": "12345",  # Invalid non-Indian short number
        "password": "Password123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_register_weak_password_validation(client: AsyncClient):
    """Test registration with weak password (missing digits) returns 422."""
    payload = {
        "full_name": "Valid Name",
        "email": "valid@example.com",
        "phone": "+919876543210",
        "password": "onlyletters",  # Missing numbers
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient):
    """Test registration with password under 8 characters returns 422."""
    payload = {
        "full_name": "Valid Name",
        "email": "valid@example.com",
        "phone": "+919876543210",
        "password": "P1!",  # Too short
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_extra_fields_forbidden(client: AsyncClient):
    """Test passing unrecognised or injected fields (like role: admin) is rejected with 422."""
    payload = {
        "full_name": "Malicious User",
        "email": "hacker@example.com",
        "phone": "+919876543210",
        "password": "Password123!",
        "role": "admin",
        "is_active": True,
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_register_name_unicode_and_smart_apostrophe(client: AsyncClient):
    """Test names with mobile smart apostrophes and Indian language scripts are accepted."""
    # Test curly apostrophe from iOS/Android keyboard
    payload_apostrophe = {
        "full_name": "Rohan O’Connor",
        "email": "rohan.oconnor@example.com",
        "phone": "+919876543211",
        "password": "Password123!",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload_apostrophe)
    assert res1.status_code == 201
    assert res1.json()["user"]["full_name"] == "Rohan O’Connor"

    # Test Devanagari script name
    payload_devanagari = {
        "full_name": "आरव शर्मा",
        "email": "aarav.dev@example.com",
        "phone": "+919876543212",
        "password": "Password123!",
    }
    res2 = await client.post("/api/v1/auth/register", json=payload_devanagari)
    assert res2.status_code == 201


@pytest.mark.asyncio
async def test_register_rate_limiting(client: AsyncClient):
    """Test exceeding RATE_LIMIT_REGISTER_MAX_ATTEMPTS from the same IP returns 429."""
    names = ["Alpha User", "Beta User", "Gamma User", "Delta User", "Epsilon User"]
    for i, name in enumerate(names):
        payload = {
            "full_name": name,
            "email": f"ratelimit{i}@example.com",
            "phone": f"+9198765432{i:02d}",
            "password": "Password123!",
        }
        res = await client.post(
            "/api/v1/auth/register",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.1"},
        )
        assert res.status_code == 201

    # 6th attempt from same IP must be rate-limited
    excess_payload = {
        "full_name": "Excess User",
        "email": "excess@example.com",
        "phone": "+919876543299",
        "password": "Password123!",
    }
    res_blocked = await client.post(
        "/api/v1/auth/register",
        json=excess_payload,
        headers={"X-Forwarded-For": "198.51.100.1"},
    )
    assert res_blocked.status_code == 429
    assert res_blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_register_proxy_headers_client_ip(client: AsyncClient):
    """Test that CF-Connecting-IP and X-Forwarded-For isolate rate limits between proxy clients."""
    # Register from IP 1
    p1 = {
        "full_name": "Proxy User Alpha",
        "email": "proxy1@example.com",
        "phone": "+919876543210",
        "password": "Password123!",
    }
    res1 = await client.post(
        "/api/v1/auth/register",
        json=p1,
        headers={"CF-Connecting-IP": "203.0.113.10"},
    )
    assert res1.status_code == 201

    # Register from IP 2 through same proxy
    p2 = {
        "full_name": "Proxy User Beta",
        "email": "proxy2@example.com",
        "phone": "+919876543211",
        "password": "Password123!",
    }
    res2 = await client.post(
        "/api/v1/auth/register",
        json=p2,
        headers={"CF-Connecting-IP": "203.0.113.20"},
    )
    assert res2.status_code == 201


@pytest.mark.asyncio
async def test_register_argon2id_stored_and_verified(
    client: AsyncClient, fake_user_repo: FakeUserRepository
):
    """Test that password is saved strictly as an Argon2id hash and verifies correctly."""
    plain_password = "MySecureArgonPassword123!"
    payload = {
        "full_name": "Argon Test User",
        "email": "argon.test@example.com",
        "phone": "+919876543210",
        "password": plain_password,
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201

    db_user = await fake_user_repo.get_by_email("argon.test@example.com")
    assert db_user is not None
    # Password must start with Argon2id signature
    assert db_user.password_hash is not None
    assert db_user.password_hash.startswith("$argon2id$")
    assert plain_password not in db_user.password_hash
    # Must verify successfully with Argon2id
    assert verify_password(plain_password, db_user.password_hash) is True


@pytest.mark.asyncio
async def test_register_concurrent_duplicate(client: AsyncClient):
    """Test simultaneous registration requests with identical email resolve safely."""
    payload = {
        "full_name": "Race User",
        "email": "race@example.com",
        "phone": "+919876543210",
        "password": "Password123!",
    }
    # Issue two registrations concurrently
    responses = await asyncio.gather(
        client.post("/api/v1/auth/register", json=payload),
        client.post("/api/v1/auth/register", json=payload),
    )
    status_codes = sorted([r.status_code for r in responses])
    # Exactly one must succeed with 201, and one must receive 409 Conflict
    assert status_codes == [201, 409]
