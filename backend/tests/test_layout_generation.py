from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.integrations.groq_client import GroqLayoutRecommendation


@pytest.mark.asyncio
async def test_generate_layout_geometric_mode_success(client: AsyncClient):
    """EP-GEO-02: Algorithmic mode generates valid, collision-free layout."""
    payload = {
        "wall": {
            "width_inches": 140.0,
            "height_inches": 96.0,
            "margin_inches": 8.0,
            "has_sofa": False,
        },
        "frames": [
            {
                "item_id": f"item-{i}",
                "photo_width_inches": 12.0,
                "photo_height_inches": 16.0,
                "matting": {"enabled": True, "top_inches": 2.0},
                "frame_profile_width_inches": 1.0,
                "orientation": "portrait",
            }
            for i in range(4)
        ],
        "spacing_inches": 3.0,
        "engine_mode": "geometric",
        "seed": 42,
    }

    response = await client.post("/api/v1/geometry/generate-layout", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["layout_type"] in ["grid", "salon", "centre", "row"]
    assert data["fits"] is True
    assert data["engine_used"] == "geometric"
    assert data["seed"] == 42
    assert len(data["items"]) == 4

    # Verify no overlaps in returned coordinates
    items = data["items"]
    for i in range(len(items)):
        a_x = items[i]["outer_x_inches"]
        a_y = items[i]["outer_y_inches"]
        a_w = items[i]["outer_width_inches"]
        a_h = items[i]["outer_height_inches"]
        for j in range(i + 1, len(items)):
            b_x = items[j]["outer_x_inches"]
            b_y = items[j]["outer_y_inches"]
            b_w = items[j]["outer_width_inches"]
            b_h = items[j]["outer_height_inches"]
            assert not (a_x < b_x + b_w and a_x + a_w > b_x and a_y < b_y + b_h and a_y + a_h > b_y)


@pytest.mark.asyncio
async def test_generate_layout_explicit_style_specified(client: AsyncClient):
    """EP-GEO-02: When layout_style is specified, engine adheres to requested style."""
    payload = {
        "wall": {
            "width_inches": 140.0,
            "height_inches": 96.0,
        },
        "frames": [
            {
                "item_id": f"f-{i}",
                "photo_width_inches": 16.0 if i == 0 else 10.0,
                "photo_height_inches": 20.0 if i == 0 else 12.0,
            }
            for i in range(5)
        ],
        "layout_style": "centre",
        "seed": 100,
    }

    response = await client.post("/api/v1/geometry/generate-layout", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["layout_type"] == "centre"


@pytest.mark.asyncio
async def test_generate_layout_smart_mode_applies_groq_recommendation(client: AsyncClient):
    """EP-GEO-02: Smart mode invokes Groq curator and translates advice to geometry."""
    mock_rec = GroqLayoutRecommendation(
        recommended_style="salon",
        focal_photo_id="item-0",
        photo_order=["item-0", "item-2", "item-1"],
        spacing_inches=4.0,
        rationale="Organic salon clustering with strong visual focal point.",
    )

    with patch(
        "app.integrations.groq_client.GroqClient.get_curator_recommendation",
        new_callable=AsyncMock,
    ) as mock_groq:
        mock_groq.return_value = (mock_rec, 215)

        payload = {
            "wall": {"width_inches": 140.0, "height_inches": 96.0},
            "frames": [
                {"item_id": "item-0", "photo_width_inches": 20.0, "photo_height_inches": 24.0},
                {"item_id": "item-1", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
                {"item_id": "item-2", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
            ],
            "engine_mode": "smart_llm",
        }

        response = await client.post("/api/v1/geometry/generate-layout", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["engine_used"] == "smart_llm"
        assert data["layout_type"] == "salon"
        assert data["ai_rationale"] == "Organic salon clustering with strong visual focal point."


@pytest.mark.asyncio
async def test_generate_layout_smart_mode_fallback_on_groq_failure(client: AsyncClient):
    """When Groq returns None / error, engine transparently falls back to geometry."""
    with patch(
        "app.integrations.groq_client.GroqClient.get_curator_recommendation",
        new_callable=AsyncMock,
    ) as mock_groq:
        # Simulate timeout or provider failure
        mock_groq.return_value = (None, 0)

        payload = {
            "wall": {"width_inches": 120.0, "height_inches": 96.0},
            "frames": [
                {"item_id": "f1", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
                {"item_id": "f2", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
            ],
            "engine_mode": "smart_llm",
        }

        response = await client.post("/api/v1/geometry/generate-layout", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["engine_used"] == "fallback_geometric"
        assert data["fits"] is True
        assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_generate_layout_deterministic_with_same_seed(client: AsyncClient):
    """Identical requests with the same seed yield exactly identical frame positions."""
    payload = {
        "wall": {"width_inches": 120.0, "height_inches": 96.0},
        "frames": [
            {"item_id": "f1", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
            {"item_id": "f2", "photo_width_inches": 14.0, "photo_height_inches": 18.0},
            {"item_id": "f3", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
        ],
        "layout_style": "salon",
        "seed": 9999,
        "variant": 0,
    }

    res1 = await client.post("/api/v1/geometry/generate-layout", json=payload)
    res2 = await client.post("/api/v1/geometry/generate-layout", json=payload)

    assert res1.json()["items"] == res2.json()["items"]
