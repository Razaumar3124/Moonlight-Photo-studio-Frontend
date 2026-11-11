from datetime import UTC, datetime, timedelta

import jwt
import pytest
from bson import ObjectId
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password, hash_token
from app.models.session import RefreshTokenInDB
from app.models.user import UserInDB
from tests.fakes import FakeSessionRepository, FakeUserRepository


@pytest.fixture(autouse=True)
async def setup_token_fixtures(
    fake_user_repo: FakeUserRepository, fake_session_repo: FakeSessionRepository
):
    """Seed user and session data for token tests."""
    now = datetime.now(UTC)
    user = UserInDB(
        _id="672cf1a9e4b0123456789abc",
        email="token.user@example.com",
        phone="+919876543210",
        password_hash=hash_password("Password123!"),
        full_name="Token Test User",
        role="customer",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    await fake_user_repo.create(user)


@pytest.mark.asyncio
async def test_get_me_success(client: AsyncClient):
    """Test GET /api/v1/auth/me with valid Bearer token returns user profile."""
    access_token, _ = create_access_token(subject="672cf1a9e4b0123456789abc", role="customer")
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == "672cf1a9e4b0123456789abc"
    assert data["email"] == "token.user@example.com"
    assert data["full_name"] == "Token Test User"


@pytest.mark.asyncio
async def test_get_me_missing_token_returns_401(client: AsyncClient):
    """Test GET /api/v1/auth/me without authorization header returns 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_get_me_expired_token_returns_401(client: AsyncClient):
    """Test GET /api/v1/auth/me with expired token returns TOKEN_EXPIRED."""
    # Create an already-expired token
    expired_token, _ = create_access_token(
        subject="672cf1a9e4b0123456789abc",
        role="customer",
        expires_delta=timedelta(seconds=-10),
    )
    headers = {"Authorization": f"Bearer {expired_token}"}

    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_get_me_tampered_signature_returns_401(client: AsyncClient):
    """Test GET /api/v1/auth/me with altered secret key returns INVALID_TOKEN."""
    fake_token = jwt.encode(
        {"sub": "672cf1a9e4b0123456789abc", "exp": 9999999999},
        "wrong-secret-key-that-is-at-least-32-bytes-long",
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {fake_token}"}

    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_refresh_token_rotation_success(
    client: AsyncClient, fake_session_repo: FakeSessionRepository
):
    """Test POST /api/v1/auth/refresh rotates the token and issues fresh access token."""
    raw_token = "valid_raw_refresh_token_12345"
    token_hash = hash_token(raw_token)
    now = datetime.now(UTC)

    session = RefreshTokenInDB(
        _id=str(ObjectId()),
        user_id="672cf1a9e4b0123456789abc",
        token_hash=token_hash,
        family_id="family-1234",
        is_revoked=False,
        expires_at=now + timedelta(days=14),
        created_at=now,
    )
    await fake_session_repo.create_refresh_token(session)

    # Call /refresh with cookie
    client.cookies.set("refresh_token", raw_token)
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != raw_token

    # Verify old token is now marked as revoked in repository
    old_doc = await fake_session_repo.get_refresh_token_by_hash(token_hash)
    assert old_doc.is_revoked is True


@pytest.mark.asyncio
async def test_refresh_token_reuse_detection_revokes_family(
    client: AsyncClient, fake_session_repo: FakeSessionRepository
):
    """Test that presenting an already-revoked refresh token triggers reuse detection."""
    raw_token = "reused_refresh_token_abc"
    token_hash = hash_token(raw_token)
    now = datetime.now(UTC)

    # Pre-revoked token in family
    session = RefreshTokenInDB(
        _id=str(ObjectId()),
        user_id="672cf1a9e4b0123456789abc",
        token_hash=token_hash,
        family_id="compromised-family-999",
        is_revoked=True,  # Already used/revoked
        expires_at=now + timedelta(days=14),
        created_at=now,
    )
    await fake_session_repo.create_refresh_token(session)

    # Attempt to use already revoked token
    client.cookies.set("refresh_token", raw_token)
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401

    data = response.json()
    assert data["error"]["code"] == "TOKEN_REVOKED"
    assert "reuse detected" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_logout_revokes_token_and_clears_cookie(
    client: AsyncClient, fake_session_repo: FakeSessionRepository
):
    """Test POST /api/v1/auth/logout revokes session in DB and clears cookie."""
    raw_token = "logout_test_token"
    token_hash = hash_token(raw_token)
    now = datetime.now(UTC)

    session = RefreshTokenInDB(
        _id=str(ObjectId()),
        user_id="672cf1a9e4b0123456789abc",
        token_hash=token_hash,
        family_id="logout-family",
        is_revoked=False,
        expires_at=now + timedelta(days=14),
        created_at=now,
    )
    await fake_session_repo.create_refresh_token(session)

    client.cookies.set("refresh_token", raw_token)
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204

    # Verify session is marked revoked in DB
    revoked_doc = await fake_session_repo.get_refresh_token_by_hash(token_hash)
    assert revoked_doc.is_revoked is True
