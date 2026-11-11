import pytest
from httpx import AsyncClient

from tests.fakes import FakePhotoRepository, FakeR2Storage
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user


@pytest.mark.asyncio
async def test_delete_photo_success(
    client: AsyncClient,
    fake_photo_repo: FakePhotoRepository,
    fake_r2_storage: FakeR2Storage,
):
    """EP-PHOTO-05: Authenticated owner can delete photo, soft-deleting in DB and purging R2."""
    _, token = await register_test_user(client, "deleter@example.com")
    raw = make_test_image(width=500, height=500, fmt="JPEG")

    up_resp = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("to_delete.jpg", raw, "image/jpeg")},
    )
    photo_id = up_resp.json()["id"]

    # Verify R2 has objects before delete
    photo_before = await fake_photo_repo.get_by_id(photo_id)
    assert photo_before.storage_key in fake_r2_storage.objects
    assert photo_before.preview_key in fake_r2_storage.objects
    assert photo_before.thumbnail_key in fake_r2_storage.objects

    # Perform delete
    response = await client.delete(
        f"/api/v1/photos/{photo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    # Verify soft-deleted in DB
    photo_after = await fake_photo_repo.get_by_id(photo_id, include_deleted=True)
    assert photo_after is not None
    assert photo_after.is_deleted is True

    # Verify purged from R2 storage
    assert photo_before.storage_key not in fake_r2_storage.objects
    assert photo_before.preview_key not in fake_r2_storage.objects
    assert photo_before.thumbnail_key not in fake_r2_storage.objects


@pytest.mark.asyncio
async def test_delete_photo_idor_protection(
    client: AsyncClient,
    fake_photo_repo: FakePhotoRepository,
):
    """EP-PHOTO-05 (IDOR Guard): Attacker cannot delete another user's photograph."""
    _, token_owner = await register_test_user(client, "victim@example.com")
    _, token_attacker = await register_test_user(client, "attacker@example.com")
    raw = make_test_image(width=400, height=400, fmt="JPEG")

    up_resp = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token_owner}"},
        files={"file": ("victim_photo.jpg", raw, "image/jpeg")},
    )
    photo_id = up_resp.json()["id"]

    # Attacker attempts to delete victim's photo
    response = await client.delete(
        f"/api/v1/photos/{photo_id}",
        headers={"Authorization": f"Bearer {token_attacker}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

    # Verify photo was NOT deleted
    photo = await fake_photo_repo.get_by_id(photo_id)
    assert photo is not None
    assert photo.is_deleted is False


@pytest.mark.asyncio
async def test_delete_nonexistent_photo_returns_404(client: AsyncClient):
    """EP-PHOTO-05: Deleting nonexistent photo ID returns 404."""
    _, token = await register_test_user(client, "delete_missing@example.com")

    response = await client.delete(
        "/api/v1/photos/672cf3a9e4b0123456789def",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_unauthenticated_returns_401(client: AsyncClient):
    """EP-PHOTO-05: Unauthenticated delete returns 401."""
    response = await client.delete("/api/v1/photos/672cf3a9e4b0123456789def")
    assert response.status_code == 401
