import pytest
from httpx import AsyncClient

from tests.fakes import FakeCatalogRepository


@pytest.mark.asyncio
async def test_list_frames_success(client: AsyncClient):
    """EP-CAT-02: Successfully retrieve frame molding profiles."""
    response = await client.get("/api/v1/frames")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert data["total"] >= 4
    assert len(data["items"]) == data["total"]

    item = data["items"][0]
    expected_fields = {
        "id",
        "sku",
        "name",
        "material_id",
        "material_name",
        "profile_width_inches",
        "profile_depth_inches",
        "rabbet_depth_inches",
        "price_per_linear_inch",
        "available_colors",
        "thumbnail_url",
        "is_active",
    }
    assert expected_fields.issubset(item.keys())
    assert isinstance(item["id"], str)
    assert isinstance(item["profile_width_inches"], float)
    assert isinstance(item["price_per_linear_inch"], str)
    assert item["is_active"] is True


@pytest.mark.asyncio
async def test_list_frames_available_colors_contain_hex_and_profile(client: AsyncClient):
    """EP-CAT-02 (Item M8 Fix): Available colors return hex swatch codes and profile width."""
    response = await client.get("/api/v1/frames")
    assert response.status_code == 200
    data = response.json()

    # Find oak box profile
    oak_box = next((f for f in data["items"] if f["sku"] == "MOLD-OAK-BOX-100"), None)
    assert oak_box is not None
    assert len(oak_box["available_colors"]) == 8

    # Verify each color has name, hex, and profile_in
    for color in oak_box["available_colors"]:
        assert "name" in color
        assert "hex" in color
        assert "profile_in" in color
        assert color["hex"].startswith("#")
        assert len(color["hex"]) == 7
        assert color["profile_in"] > 0


@pytest.mark.asyncio
async def test_list_frames_filter_by_material_id(client: AsyncClient):
    """EP-CAT-02: Filter moldings by parent material ObjectId."""
    # First get materials to pick a valid ID
    mat_resp = await client.get("/api/v1/frame-materials?category=metal")
    mat_id = mat_resp.json()["items"][0]["id"]

    response = await client.get(f"/api/v1/frames?material_id={mat_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["sku"] == "MOLD-MET-SLIM-050"
    assert data["items"][0]["material_id"] == mat_id


@pytest.mark.asyncio
async def test_list_frames_filter_by_invalid_material_id_returns_422(client: AsyncClient):
    """EP-CAT-02: Non-hexadecimal material_id returns 422 standard validation error."""
    response = await client.get("/api/v1/frames?material_id=not-valid-hex-id")
    assert response.status_code == 422
    data = response.json()

    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any(d["field"] == "material_id" for d in data["error"]["details"])


@pytest.mark.asyncio
async def test_list_frames_filter_by_nonexistent_valid_material_id(client: AsyncClient):
    """EP-CAT-02: Valid 24-hex ObjectId that does not exist returns empty list."""
    response = await client.get("/api/v1/frames?material_id=672520012e5c6a1b2c3d4e99")
    assert response.status_code == 200
    data = response.json()

    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_frames_filter_by_color(client: AsyncClient):
    """EP-CAT-02: Filter moldings offering a specific color name."""
    response = await client.get("/api/v1/frames?color=Mahogany")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] >= 1
    for item in data["items"]:
        color_names = [c["name"].lower() for c in item["available_colors"]]
        assert any("mahogany" in cn for cn in color_names)


@pytest.mark.asyncio
async def test_list_frames_filter_by_width_range(client: AsyncClient):
    """EP-CAT-02: Filter moldings by profile width range."""
    response = await client.get("/api/v1/frames?min_width=0.75&max_width=1.0")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] >= 2
    for item in data["items"]:
        assert 0.75 <= item["profile_width_inches"] <= 1.0


@pytest.mark.asyncio
async def test_list_frames_min_width_greater_than_max_returns_422(client: AsyncClient):
    """EP-CAT-02: min_width > max_width returns 422 validation error."""
    response = await client.get("/api/v1/frames?min_width=1.5&max_width=0.75")
    assert response.status_code == 422
    data = response.json()

    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any(d["field"] == "min_width" for d in data["error"]["details"])


@pytest.mark.asyncio
async def test_list_frames_negative_width_returns_422(client: AsyncClient):
    """EP-CAT-02: Negative width values are rejected with 422."""
    response = await client.get("/api/v1/frames?min_width=-0.5")
    assert response.status_code == 422
    data = response.json()

    assert "error" in data


@pytest.mark.asyncio
async def test_list_frames_empty_collection(
    client: AsyncClient,
    fake_catalog_repo: FakeCatalogRepository,
):
    """EP-CAT-02: Gracefully returns empty list when collection is empty."""
    fake_catalog_repo.moldings.clear()

    response = await client.get("/api/v1/frames")
    assert response.status_code == 200
    data = response.json()

    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_frames_public_access(client: AsyncClient):
    """EP-CAT-02: Frame moldings endpoint is publicly accessible."""
    response = await client.get("/api/v1/frames", headers={})
    assert response.status_code == 200
