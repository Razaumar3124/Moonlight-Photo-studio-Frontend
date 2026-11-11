import pytest
from httpx import AsyncClient

from tests.test_photo_upload import register_test_user


@pytest.mark.asyncio
async def test_create_design_success(client: AsyncClient):
    """EP-DSGN-01: Successfully create a new gallery wall design draft."""
    user, token = await register_test_user(client, "designer_create@example.com")

    payload = {
        "title": "Living Room Gallery Wall",
        "description": "Custom layout for dining wall",
        "wall": {
            "width_inches": 120.0,
            "height_inches": 96.0,
            "color_hex": "#F0EBE4",
            "texture": "plaster_smooth",
            "display_unit": "in",
            "has_sofa": False,
        },
    }

    response = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )

    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["user_id"] == user["id"]
    assert data["title"] == "Living Room Gallery Wall"
    assert data["description"] == "Custom layout for dining wall"
    assert data["status"] == "draft"
    assert data["current_version_id"] is None
    assert data["current_version_number"] is None
    assert data["wall"]["width_inches"] == 120.0
    assert data["wall"]["height_inches"] == 96.0
    assert data["wall"]["color_hex"] == "#F0EBE4"
    assert data["wall"]["texture"] == "plaster_smooth"
    assert data["wall"]["display_unit"] == "in"
    assert data["wall"]["has_sofa"] is False
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_design_defaults(client: AsyncClient):
    """EP-DSGN-01: Verify default wall values if optional fields are omitted."""
    _, token = await register_test_user(client, "designer_defaults@example.com")

    payload = {
        "title": "Minimal Title Only",
    }

    response = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Minimal Title Only"
    assert data["description"] is None
    assert data["wall"]["width_inches"] == 120.0
    assert data["wall"]["height_inches"] == 96.0
    assert data["wall"]["color_hex"] == "#F0EBE4"


@pytest.mark.asyncio
async def test_create_design_unauthenticated_returns_401(client: AsyncClient):
    """EP-DSGN-01: Anonymous requests are rejected with 401."""
    payload = {"title": "No Auth Design"}
    response = await client.post("/api/v1/designs", json=payload)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_create_design_validation_errors(client: AsyncClient):
    """EP-DSGN-01: Invalid dimensions or missing titles return 422."""
    _, token = await register_test_user(client, "designer_val@example.com")

    # Empty title
    res_empty = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "   "},
    )
    # Pydantic or service validation failure
    assert res_empty.status_code == 422

    # Wall too small (< 24 inches)
    res_small = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Small Wall", "wall": {"width_inches": 10.0, "height_inches": 96.0}},
    )
    assert res_small.status_code == 422

    # Invalid hex color
    res_hex = await client.post(
        "/api/v1/designs",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Bad Color", "wall": {"color_hex": "not-a-color"}},
    )
    assert res_hex.status_code == 422
