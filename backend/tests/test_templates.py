import pytest
from httpx import AsyncClient

from tests.fakes import FakeTemplateRepository


@pytest.mark.asyncio
async def test_list_templates_success(client: AsyncClient):
    """EP-TMPL-01: Successfully retrieve gallery wall templates catalog."""
    response = await client.get("/api/v1/templates")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert data["total"] == 10
    assert len(data["items"]) == 10


@pytest.mark.asyncio
async def test_list_templates_schema_conformance(client: AsyncClient):
    """EP-TMPL-01: Verify complete schema conformance for template entity."""
    response = await client.get("/api/v1/templates")
    assert response.status_code == 200
    data = response.json()

    item = data["items"][0]
    expected_fields = {
        "id",
        "slug",
        "name",
        "description",
        "category",
        "min_wall_width_inches",
        "min_wall_height_inches",
        "recommended_wall_width_inches",
        "recommended_wall_height_inches",
        "slots_count",
        "slots",
        "thumbnail_url",
    }
    assert expected_fields.issubset(item.keys())
    assert isinstance(item["id"], str)
    assert isinstance(item["slug"], str)
    assert isinstance(item["slots_count"], int)
    assert len(item["slots"]) == item["slots_count"]


@pytest.mark.asyncio
async def test_list_templates_slot_geometry(client: AsyncClient):
    """EP-TMPL-01: Verify slots contain valid coordinate ratios and opening dimensions."""
    response = await client.get("/api/v1/templates")
    assert response.status_code == 200
    data = response.json()

    grid = next((t for t in data["items"] if t["slug"] == "balanced-grid"), None)
    assert grid is not None
    assert grid["slots_count"] == 9
    assert len(grid["slots"]) == 9

    for slot in grid["slots"]:
        assert slot["slot_id"].startswith("slot-")
        assert 0.0 <= slot["relative_x_ratio"] <= 1.0
        assert 0.0 <= slot["relative_y_ratio"] <= 1.0
        assert slot["default_photo_width_inches"] > 0
        assert slot["default_photo_height_inches"] > 0
        assert slot["aspect_ratio"] > 0


@pytest.mark.asyncio
async def test_list_templates_filter_category_grid(client: AsyncClient):
    """EP-TMPL-01: Filter templates by grid category."""
    response = await client.get("/api/v1/templates?category=grid")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 3
    slugs = {t["slug"] for t in data["items"]}
    assert slugs == {"balanced-grid", "classic-six", "grand-quad"}


@pytest.mark.asyncio
async def test_list_templates_filter_category_salon(client: AsyncClient):
    """EP-TMPL-01: Filter templates by salon category."""
    response = await client.get("/api/v1/templates?category=salon")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 2
    slugs = {t["slug"] for t in data["items"]}
    assert slugs == {"creative-salon", "petite-salon"}


@pytest.mark.asyncio
async def test_list_templates_filter_category_centre_or_focal_center(client: AsyncClient):
    """EP-TMPL-01: Filter templates by centre/focal_center category."""
    resp1 = await client.get("/api/v1/templates?category=centre")
    resp2 = await client.get("/api/v1/templates?category=focal_center")
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    data1 = resp1.json()
    data2 = resp2.json()
    assert data1["total"] == 2
    assert data2["total"] == 2
    assert {t["slug"] for t in data1["items"]} == {"centre-focus", "statement-centre"}


@pytest.mark.asyncio
async def test_list_templates_filter_by_frame_count_range(client: AsyncClient):
    """EP-TMPL-01: Filter templates by slot count range (min_frames and max_frames)."""
    response = await client.get("/api/v1/templates?min_frames=4&max_frames=6")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] >= 3
    for t in data["items"]:
        assert 4 <= t["slots_count"] <= 6


@pytest.mark.asyncio
async def test_list_templates_invalid_category_returns_422(client: AsyncClient):
    """EP-TMPL-01: Unknown template category returns 422 standard validation error."""
    response = await client.get("/api/v1/templates?category=nonexistent_style")
    assert response.status_code == 422
    data = response.json()

    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any(d["field"] == "category" for d in data["error"]["details"])


@pytest.mark.asyncio
async def test_list_templates_min_frames_greater_than_max_returns_422(client: AsyncClient):
    """EP-TMPL-01: min_frames > max_frames returns 422 validation error."""
    response = await client.get("/api/v1/templates?min_frames=10&max_frames=4")
    assert response.status_code == 422
    data = response.json()

    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any(d["field"] == "min_frames" for d in data["error"]["details"])


@pytest.mark.asyncio
async def test_list_templates_negative_frames_returns_422(client: AsyncClient):
    """EP-TMPL-01: Negative frame count is rejected."""
    response = await client.get("/api/v1/templates?min_frames=0")
    assert response.status_code == 422
    data = response.json()

    assert "error" in data


@pytest.mark.asyncio
async def test_list_templates_ordering(client: AsyncClient):
    """EP-TMPL-01: Templates are ordered by slot count ascending, then name ascending."""
    response = await client.get("/api/v1/templates")
    assert response.status_code == 200
    data = response.json()

    pairs = [(t["slots_count"], t["name"]) for t in data["items"]]
    assert pairs == sorted(pairs)


@pytest.mark.asyncio
async def test_list_templates_empty_collection(
    client: AsyncClient,
    fake_template_repo: FakeTemplateRepository,
):
    """EP-TMPL-01: Returns empty list when templates collection has no records."""
    fake_template_repo.templates.clear()

    response = await client.get("/api/v1/templates")
    assert response.status_code == 200
    data = response.json()

    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_templates_public_access(client: AsyncClient):
    """EP-TMPL-01: Templates endpoint is publicly accessible."""
    response = await client.get("/api/v1/templates", headers={})
    assert response.status_code == 200
