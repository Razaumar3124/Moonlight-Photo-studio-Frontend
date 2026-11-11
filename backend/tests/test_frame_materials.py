import pytest
from httpx import AsyncClient

from tests.fakes import FakeCatalogRepository


@pytest.mark.asyncio
async def test_list_materials_success(client: AsyncClient):
    """EP-CAT-01: Successfully retrieve frame materials catalog."""
    response = await client.get("/api/v1/frame-materials")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert data["total"] >= 4
    assert len(data["items"]) == data["total"]

    # Verify first item matches contract
    item = data["items"][0]
    expected_fields = {
        "id",
        "code",
        "name",
        "category",
        "finish",
        "base_price_per_linear_inch",
        "waste_factor_percentage",
        "thumbnail_url",
        "is_available",
    }
    assert expected_fields.issubset(item.keys())
    assert isinstance(item["id"], str)
    assert isinstance(item["base_price_per_linear_inch"], str)
    assert isinstance(item["waste_factor_percentage"], float)
    assert item["is_available"] is True


@pytest.mark.asyncio
async def test_list_materials_filter_category_wood(client: AsyncClient):
    """EP-CAT-01: Filter materials by wood category."""
    response = await client.get("/api/v1/frame-materials?category=wood")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] >= 2
    for item in data["items"]:
        assert item["category"] == "wood"


@pytest.mark.asyncio
async def test_list_materials_filter_category_metal(client: AsyncClient):
    """EP-CAT-01: Filter materials by metal category."""
    response = await client.get("/api/v1/frame-materials?category=metal")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["code"] == "ALUM-01"
    assert data["items"][0]["category"] == "metal"


@pytest.mark.asyncio
async def test_list_materials_invalid_category_returns_422(client: AsyncClient):
    """EP-CAT-01: Requesting an unknown category returns 422 standard error."""
    response = await client.get("/api/v1/frame-materials?category=glass_ceramic")
    assert response.status_code == 422
    data = response.json()

    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any(d["field"] == "category" for d in data["error"]["details"])


@pytest.mark.asyncio
async def test_list_materials_sorted_by_name(client: AsyncClient):
    """EP-CAT-01: Materials are sorted alphabetically by display name."""
    response = await client.get("/api/v1/frame-materials")
    assert response.status_code == 200
    data = response.json()

    names = [item["name"] for item in data["items"]]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_list_materials_empty_collection(
    client: AsyncClient,
    fake_catalog_repo: FakeCatalogRepository,
):
    """EP-CAT-01: Gracefully returns empty list when collection has no documents."""
    fake_catalog_repo.materials.clear()

    response = await client.get("/api/v1/frame-materials")
    assert response.status_code == 200
    data = response.json()

    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_materials_public_access(client: AsyncClient):
    """EP-CAT-01: Endpoint is completely public and requires no Bearer token."""
    response = await client.get("/api/v1/frame-materials", headers={})
    assert response.status_code == 200
