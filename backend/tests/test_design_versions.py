import pytest
from httpx import AsyncClient

from tests.fakes import FakePhotoRepository
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user


@pytest.mark.asyncio
async def test_create_design_version_success(client: AsyncClient):
    """EP-DSGN-02: Create immutable version snapshot and verify sequential versioning."""
    _, token = await register_test_user(client, "versioner@example.com")

    # Create design
    design_res = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Family Wall",
            "wall": {"width_inches": 120.0, "height_inches": 96.0},
        },
    )
    design_id = design_res.json()["id"]

    # Version 1 payload
    ver1_payload = {
        "layout_type": "grid",
        "template_id": "balanced-grid",
        "items": [
            {
                "item_id": "frame-1",
                "frame_id": "frame-oak-12x16",
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
                    "color_hex": "#F4F3F3",
                },
                "glass_type": "museum_uv",
            }
        ],
    }

    res_v1 = await client.post(
        f"/api/v1/designs/{design_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json=ver1_payload,
    )
    assert res_v1.status_code == 201
    data_v1 = res_v1.json()
    assert data_v1["version_number"] == 1
    assert data_v1["layout_type"] == "grid"
    assert data_v1["items_count"] == 1
    assert data_v1["bounding_box"] == {"x": 20.0, "y": 20.0, "width": 16.0, "height": 20.0}
    # Affirm pricing engine is excluded
    assert "estimated_price" not in data_v1
    assert "pricing" not in data_v1

    # Version 2 payload (different layout/item position)
    ver2_payload = {
        "layout_type": "custom",
        "template_id": None,
        "items": [
            {
                "item_id": "frame-1",
                "frame_id": "frame-oak-12x16",
                "position_x_inches": 30.0,
                "position_y_inches": 25.0,
                "photo_width_inches": 12.0,
                "photo_height_inches": 16.0,
                "total_width_inches": 16.0,
                "total_height_inches": 20.0,
                "matting": {
                    "enabled": False,
                    "top_inches": 0,
                    "bottom_inches": 0,
                    "left_inches": 0,
                    "right_inches": 0,
                    "color_hex": "#FFFFFF",
                },
                "glass_type": "standard",
            }
        ],
    }
    res_v2 = await client.post(
        f"/api/v1/designs/{design_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json=ver2_payload,
    )
    assert res_v2.status_code == 201
    data_v2 = res_v2.json()
    assert data_v2["version_number"] == 2
    assert data_v2["version_id"] != data_v1["version_id"]

    # Verify GET /api/v1/designs/{id} reflects version 2
    detail_res = await client.get(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["status"] == "saved"
    assert detail_data["current_version_id"] == data_v2["version_id"]
    assert detail_data["current_version"]["version_number"] == 2
    assert detail_data["current_version"]["items"][0]["position_x_inches"] == 30.0
    # Affirm pricing exclusion on items
    assert "calculated_price" not in detail_data["current_version"]["items"][0]


@pytest.mark.asyncio
async def test_duplicate_version_snapshot_avoidance(client: AsyncClient):
    """EP-DSGN-02: Sending duplicate version payload returns existing version snapshot."""
    _, token = await register_test_user(client, "dedup_versioner@example.com")

    design_res = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Dedup Wall"},
    )
    design_id = design_res.json()["id"]

    ver_payload = {
        "layout_type": "grid",
        "items": [
            {
                "item_id": "frame-1",
                "frame_id": "frame-black-12x16",
                "position_x_inches": 20.0,
                "position_y_inches": 20.0,
                "photo_width_inches": 12.0,
                "photo_height_inches": 16.0,
                "total_width_inches": 16.0,
                "total_height_inches": 20.0,
                "matting": {
                    "enabled": True,
                    "top_inches": 2,
                    "bottom_inches": 2,
                    "left_inches": 2,
                    "right_inches": 2,
                    "color_hex": "#F4F3F3",
                },
                "glass_type": "standard",
            }
        ],
    }

    res_1 = await client.post(
        f"/api/v1/designs/{design_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json=ver_payload,
    )
    assert res_1.status_code == 201
    v1_id = res_1.json()["version_id"]
    assert res_1.json()["version_number"] == 1

    # Send exact same version payload
    res_2 = await client.post(
        f"/api/v1/designs/{design_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json=ver_payload,
    )
    assert res_2.status_code == 201
    assert res_2.json()["version_id"] == v1_id
    assert res_2.json()["version_number"] == 1


@pytest.mark.asyncio
async def test_version_geometry_validation_error(client: AsyncClient):
    """EP-DSGN-02: Frames that breach wall boundaries or collide are rejected."""
    _, token = await register_test_user(client, "geo_versioner@example.com")

    # Design wall is 120 x 96
    design_res = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Geo Wall", "wall": {"width_inches": 120.0, "height_inches": 96.0}},
    )
    design_id = design_res.json()["id"]

    # Frame placed at position_x = 115, width = 20 -> extends to 135 (outside 120" wall!)
    bad_payload = {
        "layout_type": "custom",
        "items": [
            {
                "item_id": "frame-out-of-bounds",
                "frame_id": "frame-oak-12x16",
                "position_x_inches": 115.0,
                "position_y_inches": 20.0,
                "photo_width_inches": 12.0,
                "photo_height_inches": 16.0,
                "total_width_inches": 20.0,
                "total_height_inches": 24.0,
                "matting": {
                    "enabled": False,
                    "top_inches": 0,
                    "bottom_inches": 0,
                    "left_inches": 0,
                    "right_inches": 0,
                    "color_hex": "#F4F3F3",
                },
                "glass_type": "standard",
            }
        ],
    }

    response = await client.post(
        f"/api/v1/designs/{design_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json=bad_payload,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_missing_photo_strategy(
    client: AsyncClient,
    fake_photo_repo: FakePhotoRepository,
):
    """EP-DSGN-03: If photo is deleted after saving design, retrieval flags photo_missing."""
    _, token = await register_test_user(client, "missing_photo_tester@example.com")

    # 1. Upload photo
    raw_img = make_test_image(width=400, height=300)
    upload_res = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("temp_photo.jpg", raw_img, "image/jpeg")},
    )
    photo_id = upload_res.json()["id"]

    # 2. Create design & version
    design_res = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Photo Missing Test Wall"},
    )
    design_id = design_res.json()["id"]

    ver_payload = {
        "layout_type": "custom",
        "items": [
            {
                "item_id": "frame-with-photo",
                "frame_id": "frame-oak-12x16",
                "photo_id": photo_id,
                "position_x_inches": 20.0,
                "position_y_inches": 20.0,
                "photo_width_inches": 12.0,
                "photo_height_inches": 16.0,
                "total_width_inches": 16.0,
                "total_height_inches": 20.0,
                "matting": {
                    "enabled": True,
                    "top_inches": 2,
                    "bottom_inches": 2,
                    "left_inches": 2,
                    "right_inches": 2,
                    "color_hex": "#F4F3F3",
                },
                "glass_type": "standard",
            }
        ],
    }
    await client.post(
        f"/api/v1/designs/{design_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json=ver_payload,
    )

    # 3. Soft-delete the photo via Photo API
    del_photo_res = await client.delete(
        f"/api/v1/photos/{photo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_photo_res.status_code == 204

    # 4. Retrieve design details: Should SUCCEED and mark photo_missing = True
    get_res = await client.get(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 200
    detail = get_res.json()
    item = detail["current_version"]["items"][0]
    assert item["photo_id"] == photo_id
    assert item["photo_missing"] is True
