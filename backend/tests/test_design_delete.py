import pytest
from bson import ObjectId
from httpx import AsyncClient

from tests.fakes import FakePhotoRepository
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user


@pytest.mark.asyncio
async def test_delete_design_success_preserves_photos(
    client: AsyncClient,
    fake_photo_repo: FakePhotoRepository,
):
    """EP-DSGN-06: Deleting a design soft-deletes it but preserves referenced photos."""
    _, token = await register_test_user(client, "deleter@example.com")

    # 1. Upload photo
    raw_img = make_test_image(width=500, height=400)
    upload_res = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("deleter_photo.jpg", raw_img, "image/jpeg")},
    )
    assert upload_res.status_code == 201
    photo_id = upload_res.json()["id"]

    # 2. Create design
    create_res = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Design to Delete"},
    )
    design_id = create_res.json()["id"]

    # 3. Create version referencing photo
    ver_payload = {
        "layout_type": "custom",
        "items": [
            {
                "item_id": "frame-del-1",
                "frame_id": "frame-mat-oak",
                "photo_id": photo_id,
                "position_x_inches": 20.0,
                "position_y_inches": 20.0,
                "photo_width_inches": 12.0,
                "photo_height_inches": 16.0,
                "total_width_inches": 16.0,
                "total_height_inches": 20.0,
                "matting": {
                    "enabled": True,
                    "top_inches": 2.0,
                    "bottom_inches": 2.0,
                    "left_inches": 2.0,
                    "right_inches": 2.0,
                    "color_hex": "#FFFFFF",
                },
                "glass_type": "standard",
            }
        ],
    }
    ver_res = await client.post(
        f"/api/v1/designs/{design_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json=ver_payload,
    )
    assert ver_res.status_code == 201

    # 4. Delete the design
    del_res = await client.delete(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204

    # 5. Verify design is no longer accessible
    get_res = await client.get(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 404

    list_res = await client.get(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_res.json()["total"] == 0

    # 6. Crucial check: Referenced photo is NOT deleted!
    photo_in_repo = await fake_photo_repo.get_by_id(photo_id)
    assert photo_in_repo is not None
    assert photo_in_repo.is_deleted is False


@pytest.mark.asyncio
async def test_delete_design_idor_denied(client: AsyncClient):
    """EP-DSGN-06: User B cannot delete User A's design."""
    _, token_a = await register_test_user(client, "owner_del_a@example.com")
    _, token_b = await register_test_user(client, "attacker_del_b@example.com")

    create_res = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Protected Wall"},
    )
    design_id = create_res.json()["id"]

    del_res = await client.delete(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert del_res.status_code == 403
    assert del_res.json()["error"]["code"] == "FORBIDDEN"

    # Verify still exists
    verify_res = await client.get(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert verify_res.status_code == 200


@pytest.mark.asyncio
async def test_delete_nonexistent_design_returns_404(client: AsyncClient):
    """EP-DSGN-06: Deleting non-existent design returns 404."""
    _, token = await register_test_user(client, "ghost_deleter@example.com")
    fake_id = str(ObjectId())

    del_res = await client.delete(
        f"/api/v1/designs/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 404
