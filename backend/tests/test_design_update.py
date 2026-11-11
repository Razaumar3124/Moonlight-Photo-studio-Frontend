import pytest
from bson import ObjectId
from httpx import AsyncClient

from tests.test_photo_upload import register_test_user


@pytest.mark.asyncio
async def test_update_design_metadata_success(client: AsyncClient):
    """EP-DSGN-05: Authenticated owner can patch design title, description, wall, and status."""
    _, token = await register_test_user(client, "updater_designer@example.com")

    # Create initial design
    create_res = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Old Gallery Title", "description": "Initial draft"},
    )
    design_id = create_res.json()["id"]

    # Patch updates
    patch_payload = {
        "title": "Updated Gallery Title",
        "description": "Revised dining layout",
        "status": "saved",
        "wall": {
            "width_inches": 140.0,
            "height_inches": 100.0,
            "color_hex": "#CCCCCC",
            "texture": "brick_white",
            "display_unit": "cm",
            "has_sofa": True,
        },
    }

    patch_res = await client.patch(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=patch_payload,
    )

    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["id"] == design_id
    assert data["title"] == "Updated Gallery Title"
    assert data["description"] == "Revised dining layout"
    assert data["status"] == "saved"
    assert data["wall"]["width_inches"] == 140.0
    assert data["wall"]["height_inches"] == 100.0
    assert data["wall"]["color_hex"] == "#CCCCCC"
    assert data["wall"]["texture"] == "brick_white"
    assert data["wall"]["display_unit"] == "cm"
    assert data["wall"]["has_sofa"] is True


@pytest.mark.asyncio
async def test_update_design_nonexistent_returns_404(client: AsyncClient):
    """EP-DSGN-05: Non-existent design ID returns 404."""
    _, token = await register_test_user(client, "notfound_updater@example.com")
    fake_id = str(ObjectId())

    response = await client.patch(
        f"/api/v1/designs/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Doesn't Matter"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_design_idor_denied(client: AsyncClient):
    """EP-DSGN-05: User B cannot modify User A's design."""
    _, token_a = await register_test_user(client, "owner_a@example.com")
    _, token_b = await register_test_user(client, "attacker_b@example.com")

    # User A creates design
    create_res = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "User A Private Wall"},
    )
    design_id = create_res.json()["id"]

    # User B attempts to patch it
    patch_res = await client.patch(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "Hacked Title"},
    )
    assert patch_res.status_code == 403
    assert patch_res.json()["error"]["code"] == "FORBIDDEN"

    # Verify original title intact
    get_res = await client.get(
        f"/api/v1/designs/{design_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert get_res.json()["title"] == "User A Private Wall"
