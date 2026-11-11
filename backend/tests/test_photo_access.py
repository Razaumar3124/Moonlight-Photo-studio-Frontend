import pytest
from httpx import AsyncClient

from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user


@pytest.mark.asyncio
async def test_access_thumbnail_with_signed_url_success(client: AsyncClient):
    """EP-PHOTO-03: Access thumbnail via HMAC signed query parameter."""
    _, token = await register_test_user(client, "media_signer@example.com")
    raw = make_test_image(width=500, height=500, fmt="JPEG")

    up_resp = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo.jpg", raw, "image/jpeg")},
    )
    thumb_url = up_resp.json()["thumbnail_url"]

    # Public-like request using only signed URL (simulates browser <img src="...">)
    response = await client.get(thumb_url)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert "private, max-age=86400" in response.headers["cache-control"]
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_access_preview_with_signed_url_success(client: AsyncClient):
    """EP-PHOTO-04: Access preview via HMAC signed query parameter."""
    _, token = await register_test_user(client, "preview_signer@example.com")
    raw = make_test_image(width=600, height=400, fmt="JPEG")

    up_resp = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo.jpg", raw, "image/jpeg")},
    )
    prev_url = up_resp.json()["preview_url"]

    response = await client.get(prev_url)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_access_with_tampered_signature_returns_403(client: AsyncClient):
    """EP-PHOTO-03: Tampered signature rejected with 403 Forbidden."""
    _, token = await register_test_user(client, "tamper@example.com")
    raw = make_test_image(width=400, height=400, fmt="JPEG")

    up_resp = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo.jpg", raw, "image/jpeg")},
    )
    photo_id = up_resp.json()["id"]

    response = await client.get(
        f"/api/v1/photos/{photo_id}/thumbnail?sig=tampered_sig_123&exp=9999999999"
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_access_with_expired_signature_returns_403(client: AsyncClient):
    """EP-PHOTO-03: Expired signature rejected with 403 Forbidden."""
    _, token = await register_test_user(client, "expired@example.com")
    raw = make_test_image(width=400, height=400, fmt="JPEG")

    up_resp = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo.jpg", raw, "image/jpeg")},
    )
    photo_id = up_resp.json()["id"]

    # Past epoch timestamp
    response = await client.get(
        f"/api/v1/photos/{photo_id}/thumbnail?sig=validformat123456&exp=1000000000"
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_access_with_owner_bearer_token_without_sig(client: AsyncClient):
    """EP-PHOTO-03: Authenticated owner can access without HMAC signature parameter."""
    _, token = await register_test_user(client, "owner_direct@example.com")
    raw = make_test_image(width=400, height=400, fmt="JPEG")

    up_resp = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo.jpg", raw, "image/jpeg")},
    )
    photo_id = up_resp.json()["id"]

    response = await client.get(
        f"/api/v1/photos/{photo_id}/thumbnail",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"


@pytest.mark.asyncio
async def test_access_with_non_owner_bearer_token_returns_403(client: AsyncClient):
    """EP-PHOTO-03 (IDOR Guard): Non-owner Bearer token rejected with 403."""
    _, token_owner = await register_test_user(client, "photo_owner@example.com")
    _, token_attacker = await register_test_user(client, "photo_attacker@example.com")
    raw = make_test_image(width=400, height=400, fmt="JPEG")

    up_resp = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token_owner}"},
        files={"file": ("private.jpg", raw, "image/jpeg")},
    )
    photo_id = up_resp.json()["id"]

    response = await client.get(
        f"/api/v1/photos/{photo_id}/thumbnail",
        headers={"Authorization": f"Bearer {token_attacker}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_access_nonexistent_photo_returns_404(client: AsyncClient):
    """EP-PHOTO-03: Accessing nonexistent photo ID returns 404."""
    response = await client.get(
        "/api/v1/photos/672cf3a9e4b0123456789def/thumbnail?sig=dummy&exp=9999999999"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
