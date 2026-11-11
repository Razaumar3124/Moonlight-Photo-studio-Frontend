import pytest
from httpx import AsyncClient

from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user


@pytest.mark.asyncio
async def test_idor_get_design_denied(client: AsyncClient):
    """EP-DSGN-03: User B is forbidden from reading User A's design."""
    _, token_a = await register_test_user(client, "victim_a@example.com")
    _, token_b = await register_test_user(client, "attacker_b@example.com")

    # User A creates a design
    res_a = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Secret Personal Design"},
    )
    design_id = res_a.json()["id"]

    # User B tries to read User A's design
    res_b = await client.get(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b.status_code == 403
    assert res_b.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_idor_create_version_denied(client: AsyncClient):
    """EP-DSGN-02: User B cannot append versions to User A's design."""
    _, token_a = await register_test_user(client, "victim_v_a@example.com")
    _, token_b = await register_test_user(client, "attacker_v_b@example.com")

    res_a = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Victim Design"},
    )
    design_id = res_a.json()["id"]

    # User B attempts to save a version into User A's design
    payload = {
        "layout_type": "grid",
        "items": [
            {
                "item_id": "frame-hack-1",
                "frame_id": "frame-oak-12x16",
                "position_x_inches": 20.0,
                "position_y_inches": 20.0,
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
                    "color_hex": "#F4F3F3",
                },
                "glass_type": "standard",
            }
        ],
    }
    res_b = await client.post(
        f"/api/v1/designs/{design_id}/versions",
        headers={"Authorization": f"Bearer {token_b}"},
        json=payload,
    )
    assert res_b.status_code == 403
    assert res_b.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_cross_user_photo_reference_prevented(client: AsyncClient):
    """EP-DSGN-02: User B cannot attach User A's private photo to their design."""
    _, token_a = await register_test_user(client, "photo_owner_a@example.com")
    _, token_b = await register_test_user(client, "design_creator_b@example.com")

    # 1. User A uploads a private photo
    raw_img = make_test_image(width=500, height=400)
    upload_res = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("usera_private.jpg", raw_img, "image/jpeg")},
    )
    photo_a_id = upload_res.json()["id"]

    # 2. User B creates their own design
    design_b_res = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "User B Wall"},
    )
    design_b_id = design_b_res.json()["id"]

    # 3. User B attempts to attach User A's photo to User B's design version
    malicious_payload = {
        "layout_type": "custom",
        "items": [
            {
                "item_id": "frame-stolen-photo",
                "frame_id": "frame-oak-12x16",
                "photo_id": photo_a_id,  # Owned by User A!
                "position_x_inches": 20.0,
                "position_y_inches": 20.0,
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
                    "color_hex": "#F4F3F3",
                },
                "glass_type": "standard",
            }
        ],
    }

    res_stolen = await client.post(
        f"/api/v1/designs/{design_b_id}/versions",
        headers={"Authorization": f"Bearer {token_b}"},
        json=malicious_payload,
    )
    # Must be rejected with 403 Forbidden!
    assert res_stolen.status_code == 403
    assert res_stolen.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_malformed_object_id_handling(client: AsyncClient):
    """Endpoints safely reject malformed non-hex MongoDB ObjectIds."""
    _, token = await register_test_user(client, "malformed_id_tester@example.com")

    # Malformed design ID
    response = await client.get(
        "/api/v1/designs/not-a-valid-object-id-123",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (404, 422)
    assert "error" in response.json()


@pytest.mark.asyncio
async def test_no_pricing_fields_in_design_responses(client: AsyncClient):
    """Strict verification that pricing engine fields are excluded across all Phase 6 responses."""
    _, token = await register_test_user(client, "no_pricing_user@example.com")

    # 1. Create design
    create_res = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Clean Scope Wall"},
    )
    design_id = create_res.json()["id"]
    create_text = create_res.text.lower()
    for forbidden in ["price", "pricing", "quotation", "gst", "shipping", "tax", "subtotal"]:
        assert forbidden not in create_text

    # 2. Add version
    ver_res = await client.post(
        f"/api/v1/designs/{design_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "layout_type": "grid",
            "items": [
                {
                    "item_id": "frame-scope-1",
                    "frame_id": "frame-oak-12x16",
                    "position_x_inches": 20.0,
                    "position_y_inches": 20.0,
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
                        "color_hex": "#F4F3F3",
                    },
                    "glass_type": "standard",
                }
            ],
        },
    )
    ver_text = ver_res.text.lower()
    for forbidden in ["price", "pricing", "quotation", "gst", "shipping", "tax", "subtotal"]:
        assert forbidden not in ver_text

    # 3. Retrieve design detail
    detail_res = await client.get(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    detail_text = detail_res.text.lower()
    for forbidden in ["price", "pricing", "quotation", "gst", "shipping", "tax", "subtotal"]:
        assert forbidden not in detail_text

    # 4. List designs
    list_res = await client.get(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
    )
    list_text = list_res.text.lower()
    for forbidden in ["price", "pricing", "quotation", "gst", "shipping", "tax", "subtotal"]:
        assert forbidden not in list_text
