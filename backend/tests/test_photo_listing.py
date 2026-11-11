import pytest
from httpx import AsyncClient

from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user


@pytest.mark.asyncio
async def test_list_photos_returns_user_photos(client: AsyncClient):
    """EP-PHOTO-02: Authenticated user can list their uploaded photos."""
    _, token = await register_test_user(client, "lister@example.com")
    raw = make_test_image(width=500, height=400, fmt="JPEG")

    # Upload two photos
    await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo1.jpg", raw, "image/jpeg")},
    )
    await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo2.jpg", raw, "image/jpeg")},
    )

    response = await client.get(
        "/api/v1/photos",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert all("thumbnail_url" in item for item in data["items"])
    assert all("sig=" in item["thumbnail_url"] for item in data["items"])


@pytest.mark.asyncio
async def test_list_photos_ownership_isolation(client: AsyncClient):
    """EP-PHOTO-02: User A's photo listing does not leak User B's photographs."""
    _, token_a = await register_test_user(client, "user_a@example.com")
    _, token_b = await register_test_user(client, "user_b@example.com")
    raw = make_test_image(width=450, height=350, fmt="PNG")

    # User A uploads a photo
    await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("usera_private.png", raw, "image/png")},
    )

    # User B lists photos
    response_b = await client.get(
        "/api/v1/photos",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response_b.status_code == 200
    data_b = response_b.json()
    assert data_b["total"] == 0
    assert data_b["items"] == []


@pytest.mark.asyncio
async def test_list_photos_unauthenticated_returns_401(client: AsyncClient):
    """EP-PHOTO-02: Missing Bearer token returns 401."""
    response = await client.get("/api/v1/photos")
    assert response.status_code == 401
