from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.fakes import FakeUserRepository


@pytest.mark.asyncio
async def test_google_auth_new_user_success(
    client: AsyncClient, fake_user_repo: FakeUserRepository
):
    """Test authenticating with a valid Google ID token registers a new user."""
    mock_id_info = {
        "sub": "google-sub-123456",
        "email": "google.user@example.com",
        "email_verified": True,
        "name": "Google Test User",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        payload = {"id_token": "valid_mock_google_id_token"}
        response = await client.post("/api/v1/auth/google", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["user"]["email"] == "google.user@example.com"
        assert data["user"]["full_name"] == "Google Test User"
        assert "access_token" in data["tokens"]
        assert "refresh_token" not in data["tokens"]
        assert "refresh_token" in response.cookies

        # Verify user was saved with google_id
        db_user = await fake_user_repo.get_by_email("google.user@example.com")
        assert db_user is not None
        assert db_user.google_id == "google-sub-123456"
        assert db_user.auth_provider == "google"


@pytest.mark.asyncio
async def test_google_auth_link_existing_user_success(
    client: AsyncClient, fake_user_repo: FakeUserRepository
):
    """Test authenticating with Google links google_id to existing account with same email."""
    from datetime import UTC, datetime

    from bson import ObjectId

    from app.core.security import hash_password
    from app.models.user import UserInDB

    # Pre-register local user with matching email
    now = datetime.now(UTC)
    existing_user = UserInDB(
        _id=str(ObjectId()),
        email="existing.local@example.com",
        phone="+919876543210",
        password_hash=hash_password("Password123!"),
        full_name="Local User",
        role="customer",
        is_active=True,
        google_id=None,
        created_at=now,
        updated_at=now,
    )
    await fake_user_repo.create(existing_user)

    mock_id_info = {
        "sub": "google-sub-789012",
        "email": "existing.local@example.com",
        "email_verified": True,
        "name": "Local User",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        payload = {"id_token": "valid_token_for_existing_user"}
        response = await client.post("/api/v1/auth/google", json=payload)
        assert response.status_code == 200

        # Verify Google ID linked to existing account
        updated_user = await fake_user_repo.get_by_email("existing.local@example.com")
        assert updated_user.google_id == "google-sub-789012"


@pytest.mark.asyncio
async def test_google_auth_invalid_token_returns_401(client: AsyncClient):
    """Test invalid Google token returns 401 with INVALID_GOOGLE_TOKEN."""
    with patch(
        "google.oauth2.id_token.verify_oauth2_token", side_effect=ValueError("Token invalid")
    ):
        payload = {"id_token": "forged_or_expired_google_token"}
        response = await client.post("/api/v1/auth/google", json=payload)
        assert response.status_code == 401

        data = response.json()
        assert data["error"]["code"] == "INVALID_GOOGLE_TOKEN"


@pytest.mark.asyncio
async def test_google_auth_unverified_email_returns_401(client: AsyncClient):
    """Test Google token with unverified email returns 401."""
    mock_id_info = {
        "sub": "google-sub-unverified",
        "email": "unverified@example.com",
        "email_verified": False,  # Not verified by Google
        "name": "Unverified User",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        payload = {"id_token": "token_with_unverified_email"}
        response = await client.post("/api/v1/auth/google", json=payload)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_GOOGLE_TOKEN"


@pytest.mark.asyncio
async def test_google_auth_disabled_account_returns_403(
    client: AsyncClient, fake_user_repo: FakeUserRepository
):
    """Test Google auth with email matching disabled account returns 403."""
    from datetime import UTC, datetime

    from bson import ObjectId

    from app.models.user import UserInDB

    now = datetime.now(UTC)
    disabled_user = UserInDB(
        _id=str(ObjectId()),
        email="disabled.user@example.com",
        phone="+919876543211",
        password_hash=None,
        full_name="Disabled User",
        role="customer",
        is_active=False,
        google_id=None,
        created_at=now,
        updated_at=now,
    )
    await fake_user_repo.create(disabled_user)

    mock_id_info = {
        "sub": "google-sub-disabled",
        "email": "disabled.user@example.com",
        "email_verified": True,
        "name": "Disabled User",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        payload = {"id_token": "valid_token_for_disabled_user"}
        response = await client.post("/api/v1/auth/google", json=payload)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"


@pytest.mark.asyncio
async def test_google_auth_conflicting_google_id_returns_401(
    client: AsyncClient, fake_user_repo: FakeUserRepository
):
    """Test Google auth with email already linked to different google_id returns 401."""
    from datetime import UTC, datetime

    from bson import ObjectId

    from app.models.user import UserInDB

    now = datetime.now(UTC)
    existing_user = UserInDB(
        _id=str(ObjectId()),
        email="linked.user@example.com",
        phone=None,
        password_hash=None,
        full_name="Linked User",
        role="customer",
        is_active=True,
        google_id="first-google-id",
        created_at=now,
        updated_at=now,
    )
    await fake_user_repo.create(existing_user)

    mock_id_info = {
        "sub": "different-google-id",
        "email": "linked.user@example.com",
        "email_verified": True,
        "name": "Linked User",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        payload = {"id_token": "valid_token_with_conflict"}
        response = await client.post("/api/v1/auth/google", json=payload)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_GOOGLE_TOKEN"


@pytest.mark.asyncio
async def test_google_auth_fails_closed_without_client_id(client: AsyncClient):
    """Without GOOGLE_CLIENT_ID the token audience can't be checked: refuse, never verify."""
    from app.core.config import get_settings

    settings = get_settings().model_copy(update={"GOOGLE_CLIENT_ID": "  "})
    with (
        patch("app.services.google_auth_service.get_settings", return_value=settings),
        patch("google.oauth2.id_token.verify_oauth2_token") as verify,
    ):
        response = await client.post("/api/v1/auth/google", json={"id_token": "any-google-token"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "GOOGLE_AUTH_NOT_CONFIGURED"
    verify.assert_not_called()


@pytest.mark.asyncio
async def test_google_auth_checks_configured_audience(client: AsyncClient):
    mock_id_info = {"sub": "g-aud", "email": "aud@example.com", "email_verified": True}
    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info) as verify:
        response = await client.post("/api/v1/auth/google", json={"id_token": "valid-token-123"})

    assert response.status_code == 200
    assert verify.call_args.kwargs["audience"] == "test-google-client-id.apps.googleusercontent.com"
