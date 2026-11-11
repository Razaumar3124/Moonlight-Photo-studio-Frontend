import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_validate_layout_valid_arrangement(client: AsyncClient):
    """EP-GEO-01: Valid non-overlapping arrangement returns 200 with is_valid=True."""
    payload = {
        "wall": {
            "width_inches": 120.0,
            "height_inches": 96.0,
            "margin_inches": 6.0,
            "has_sofa": False,
        },
        "frames": [
            {
                "item_id": "frame-1",
                "outer_x_inches": 20.0,
                "outer_y_inches": 20.0,
                "outer_width_inches": 18.0,
                "outer_height_inches": 22.0,
            },
            {
                "item_id": "frame-2",
                "outer_x_inches": 42.0,
                "outer_y_inches": 20.0,
                "outer_width_inches": 18.0,
                "outer_height_inches": 22.0,
            },
        ],
    }

    response = await client.post("/api/v1/geometry/validate-layout", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["is_valid"] is True
    assert data["errors"] == []
    assert data["wall_coverage_percentage"] > 0
    assert len(data["calculated_items"]) == 2
    assert data["bounding_box"]["x"] == 20.0
    assert data["bounding_box"]["width"] == 40.0  # 60 - 20


@pytest.mark.asyncio
async def test_validate_layout_collision_detected(client: AsyncClient):
    """EP-GEO-01: Overlapping frames return 200 with is_valid=False and collision details."""
    payload = {
        "wall": {
            "width_inches": 120.0,
            "height_inches": 96.0,
            "margin_inches": 6.0,
        },
        "frames": [
            {
                "item_id": "frame-1",
                "outer_x_inches": 20.0,
                "outer_y_inches": 20.0,
                "outer_width_inches": 20.0,
                "outer_height_inches": 20.0,
            },
            {
                "item_id": "frame-2",
                "outer_x_inches": 30.0,  # Overlaps frame-1 (x: 20-40)
                "outer_y_inches": 20.0,
                "outer_width_inches": 20.0,
                "outer_height_inches": 20.0,
            },
        ],
    }

    response = await client.post("/api/v1/geometry/validate-layout", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["is_valid"] is False
    assert len(data["errors"]) >= 1
    err = data["errors"][0]
    assert err["code"] == "GEOMETRY_COLLISION_DETECTED"
    assert "frame-1" in err["item_ids"]
    assert "frame-2" in err["item_ids"]
    assert data["calculated_items"] == []


@pytest.mark.asyncio
async def test_validate_layout_out_of_bounds(client: AsyncClient):
    """EP-GEO-01: Frame extending outside safe margins returns is_valid=False."""
    payload = {
        "wall": {
            "width_inches": 100.0,
            "height_inches": 80.0,
            "margin_inches": 8.0,
        },
        "frames": [
            {
                "item_id": "frame-out",
                "outer_x_inches": 95.0,  # 95 + 10 = 105 > (100 - 8 = 92)
                "outer_y_inches": 20.0,
                "outer_width_inches": 10.0,
                "outer_height_inches": 10.0,
            }
        ],
    }

    response = await client.post("/api/v1/geometry/validate-layout", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["is_valid"] is False
    assert any(e["code"] == "GEOMETRY_OUT_OF_BOUNDS" for e in data["errors"])


@pytest.mark.asyncio
async def test_validate_layout_empty_frames_returns_422(client: AsyncClient):
    """Malformed request with empty frames list returns 422 Unprocessable Content."""
    payload = {
        "wall": {
            "width_inches": 120.0,
            "height_inches": 96.0,
        },
        "frames": [],
    }

    response = await client.post("/api/v1/geometry/validate-layout", json=payload)
    assert response.status_code == 422
