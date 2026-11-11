import pytest
from httpx import AsyncClient

from tests.fakes import FakeUserRepository


@pytest.fixture(autouse=True)
async def setup_test_user(fake_user_repo: FakeUserRepository):
    """Seed a test customer account."""
    from datetime import UTC, datetime

    from bson import ObjectId

    from app.core.security import hash_password
    from app.models.user import UserInDB

    now = datetime.now(UTC)
    user = UserInDB(
        _id=str(ObjectId()),
        email="customer@example.com",
        phone="+919876543210",
        password_hash=hash_password("ValidPassword123!"),
        full_name="Aarav Sharma",
        role="customer",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    await fake_user_repo.create(user)

    # Disabled account
    disabled_user = UserInDB(
        _id=str(ObjectId()),
        email="disabled@example.com",
        phone="+919876543219",
        password_hash=hash_password("ValidPassword123!"),
        full_name="Disabled User",
        role="customer",
        is_active=False,
        created_at=now,
        updated_at=now,
    )
    await fake_user_repo.create(disabled_user)


@pytest.mark.asyncio
async def test_login_with_email_success(client: AsyncClient):
    """Test login with email and password returns 200 with tokens and sets cookie."""
    payload = {
        "email": "customer@example.com",
        "password": "ValidPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["user"]["email"] == "customer@example.com"
    assert data["user"]["full_name"] == "Aarav Sharma"
    assert data["tokens"]["token_type"] == "bearer"
    assert "access_token" in data["tokens"]
    assert "refresh_token" in data["tokens"]
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_with_phone_success(client: AsyncClient):
    """Test login with Indian mobile phone returns 200."""
    payload = {
        "phone": "+919876543210",
        "password": "ValidPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    assert response.json()["user"]["phone"] == "+919876543210"


@pytest.mark.asyncio
async def test_login_with_identifier_field_email(client: AsyncClient):
    """Test login with combined identifier field containing email."""
    payload = {
        "identifier": "customer@example.com",
        "password": "ValidPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "customer@example.com"


@pytest.mark.asyncio
async def test_login_with_identifier_field_phone(client: AsyncClient):
    """Test login with combined identifier field containing mobile number."""
    payload = {
        "identifier": "9876543210",  # Unprefixed 10 digits
        "password": "ValidPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    assert response.json()["user"]["phone"] == "+919876543210"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient):
    """Test wrong password returns 401 with standard generic message."""
    payload = {
        "email": "customer@example.com",
        "password": "WrongPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401

    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"
    assert "Those details don’t match our records" in data["error"]["message"]


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_identical_401(client: AsyncClient):
    """Test non-existent account returns the identical 401 (preventing enumeration)."""
    payload = {
        "email": "unknown.person@example.com",
        "password": "AnyPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401

    data = response.json()
    assert data["error"]["code"] == "INVALID_CREDENTIALS"
    assert "Those details don’t match our records" in data["error"]["message"]


@pytest.mark.asyncio
async def test_login_disabled_account_returns_403(client: AsyncClient):
    """Test deactivated account returns 403 Forbidden with ACCOUNT_DISABLED."""
    payload = {
        "email": "disabled@example.com",
        "password": "ValidPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"
