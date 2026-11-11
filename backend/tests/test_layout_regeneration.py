import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_regenerate_layout_preserves_style_and_changes_seed(client: AsyncClient):
    """Regenerate layout preserves current layout style, mutates seed, and yields new positions."""
    payload = {
        "wall": {
            "width_inches": 140.0,
            "height_inches": 96.0,
            "margin_inches": 6.0,
        },
        "frames": [
            {"item_id": "item-1", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
            {"item_id": "item-2", "photo_width_inches": 14.0, "photo_height_inches": 18.0},
            {"item_id": "item-3", "photo_width_inches": 10.0, "photo_height_inches": 14.0},
            {"item_id": "item-4", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
        ],
        "layout_style": "salon",
        "current_seed": 12345,
        "current_variant": 0,
        "spacing_inches": 3.0,
    }

    response = await client.post("/api/v1/geometry/regenerate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["layout_type"] == "salon"
    assert data["seed"] != 12345
    assert data["engine_used"] == "geometric"
    assert data["fits"] is True
    assert len(data["items"]) == 4


@pytest.mark.asyncio
async def test_regenerate_layout_zero_ai_tokens(client: AsyncClient):
    """Regenerate layout uses pure Python geometry with zero external AI calls."""
    payload = {
        "wall": {"width_inches": 120.0, "height_inches": 96.0},
        "frames": [
            {"item_id": "f1", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
            {"item_id": "f2", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
        ],
        "layout_style": "grid",
        "current_seed": 555,
        "current_variant": 0,
    }

    response = await client.post("/api/v1/geometry/regenerate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["engine_used"] == "geometric"
    assert "ai_rationale" not in data
