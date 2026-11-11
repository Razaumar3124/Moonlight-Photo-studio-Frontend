from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import Settings
from app.integrations.groq_client import GroqClient, GroqLayoutRecommendation
from app.repositories.ai_cache_repository import AICacheRepository
from app.services.ai_usage_service import AIUsageService


def test_ai_usage_service_limits():
    """AIUsageService blocks callers exceeding daily request limits or token budget."""
    settings = Settings(
        GROQ_DAILY_REQUEST_LIMIT=2,
        GROQ_DAILY_TOKEN_BUDGET=500,
    )
    service = AIUsageService(settings)

    caller = "user-abc"
    assert service.can_make_request(caller) is True

    # 1st request
    service.record_usage(caller, tokens_used=100)
    assert service.can_make_request(caller) is True

    # 2nd request
    service.record_usage(caller, tokens_used=150)
    # Caller reached limit of 2 requests
    assert service.can_make_request(caller) is False

    # Another caller can still make requests
    assert service.can_make_request("user-xyz") is True

    # Global token budget exceeded
    service.record_usage("user-xyz", tokens_used=300)  # Total: 100 + 150 + 300 = 550 > 500
    assert service.can_make_request("user-xyz") is False


def test_ai_cache_repository_hit_and_miss():
    """AICacheRepository correctly caches and retrieves recommendations by key."""
    repo = AICacheRepository(ttl_hours=1)

    wall = {"width_inches": 120.0, "height_inches": 96.0}
    photos = [
        {"item_id": "p1", "aspect_ratio": 1.5, "orientation": "landscape"},
        {"item_id": "p2", "aspect_ratio": 0.67, "orientation": "portrait"},
    ]

    key = repo.compute_cache_key(wall=wall, photos=photos, current_style="grid")
    assert isinstance(key, str) and len(key) == 64

    # Cache miss
    assert repo.get(key) is None

    # Cache set & hit
    rec = GroqLayoutRecommendation(
        recommended_style="salon",
        focal_photo_id="p2",
        photo_order=["p2", "p1"],
        spacing_inches=3.0,
        rationale="Curated balance",
    )
    repo.set(key, rec)
    cached = repo.get(key)
    assert cached is not None
    assert cached.recommended_style == "salon"
    assert cached.photo_order == ["p2", "p1"]


@pytest.mark.asyncio
async def test_groq_client_successful_parsing():
    """GroqClient parses valid JSON response and extracts token usage."""
    settings = Settings(
        GROQ_ENABLED=True,
        GROQ_API_KEY="mock-groq-key",
    )

    mock_http_response = httpx.Response(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"recommended_style": "centre", "focal_photo_id": "f1", '
                            '"photo_order": ["f1", "f2"], "spacing_inches": 3.0, '
                            '"rationale": "Harmonious"}'
                        )
                    }
                }
            ],
            "usage": {"total_tokens": 195},
        },
    )

    mock_http_client = AsyncMock(spec=httpx.AsyncClient)
    mock_http_client.post.return_value = mock_http_response

    client = GroqClient(settings=settings, client=mock_http_client)
    wall = {"width_inches": 120.0, "height_inches": 96.0}
    photos = [
        {"item_id": "f1", "aspect_ratio": 1.5, "orientation": "landscape"},
        {"item_id": "f2", "aspect_ratio": 0.75, "orientation": "portrait"},
    ]

    rec, tokens = await client.get_curator_recommendation(wall, photos)
    assert rec is not None
    assert rec.recommended_style == "centre"
    assert rec.focal_photo_id == "f1"
    assert tokens == 195


@pytest.mark.asyncio
async def test_groq_client_rate_limit_and_timeout_returns_none():
    """GroqClient handles rate limit (429) or timeouts cleanly without raising."""
    settings = Settings(
        GROQ_ENABLED=True,
        GROQ_API_KEY="mock-groq-key",
    )

    # 429 response
    mock_http_response_429 = httpx.Response(status_code=429, text="Rate limit exceeded")
    mock_http_client = AsyncMock(spec=httpx.AsyncClient)
    mock_http_client.post.return_value = mock_http_response_429

    client = GroqClient(settings=settings, client=mock_http_client)
    rec, tokens = await client.get_curator_recommendation({"width_inches": 100}, [{"item_id": "1"}])
    assert rec is None
    assert tokens == 0


@pytest.mark.asyncio
async def test_groq_client_disabled_when_no_key():
    """When GROQ_ENABLED is False or API key is empty, client returns None instantly (0 tokens)."""
    settings = Settings(
        GROQ_ENABLED=False,
        GROQ_API_KEY="",
    )
    client = GroqClient(settings=settings)
    rec, tokens = await client.get_curator_recommendation({"width_inches": 100}, [{"item_id": "1"}])
    assert rec is None
    assert tokens == 0
