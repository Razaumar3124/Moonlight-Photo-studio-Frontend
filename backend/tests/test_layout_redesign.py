from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.integrations.groq_client import GroqLayoutRecommendation


@pytest.mark.asyncio
async def test_redesign_layout_geometric_archetype_shift(client: AsyncClient):
    """Redesign layout cycles to next compositional archetype by default."""
    payload = {
        "wall": {
            "width_inches": 140.0,
            "height_inches": 96.0,
        },
        "frames": [
            {"item_id": "f1", "photo_width_inches": 16.0, "photo_height_inches": 20.0},
            {"item_id": "f2", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
            {"item_id": "f3", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
        ],
        "current_layout_style": "grid",
        "engine_mode": "geometric",
    }

    response = await client.post("/api/v1/geometry/redesign", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["layout_type"] != "grid"
    assert data["layout_type"] in ["salon", "centre", "row"]
    assert data["engine_used"] == "geometric"
    assert data["fits"] is True


@pytest.mark.asyncio
async def test_redesign_layout_smart_mode_with_groq(client: AsyncClient):
    """Smart redesign requests fresh creative direction from Groq curator."""
    mock_rec = GroqLayoutRecommendation(
        recommended_style="centre",
        focal_photo_id="f1",
        photo_order=["f1", "f2", "f3"],
        spacing_inches=3.5,
        rationale="Switching to a focal center composition for visual grandeur.",
    )

    with patch(
        "app.integrations.groq_client.GroqClient.get_curator_recommendation",
        new_callable=AsyncMock,
    ) as mock_groq:
        mock_groq.return_value = (mock_rec, 185)

        payload = {
            "wall": {"width_inches": 140.0, "height_inches": 96.0},
            "frames": [
                {"item_id": "f1", "photo_width_inches": 16.0, "photo_height_inches": 20.0},
                {"item_id": "f2", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
                {"item_id": "f3", "photo_width_inches": 12.0, "photo_height_inches": 16.0},
            ],
            "current_layout_style": "salon",
            "engine_mode": "smart_llm",
        }

        response = await client.post("/api/v1/geometry/redesign", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["layout_type"] == "centre"
        assert data["engine_used"] == "smart_llm"
        expected_rationale = "Switching to a focal center composition for visual grandeur."
        assert data["ai_rationale"] == expected_rationale
