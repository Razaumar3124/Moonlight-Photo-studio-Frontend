import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core import limits
from app.core.config import Settings
from app.integrations.groq_client import GroqClient, GroqLayoutRecommendation
from app.repositories.ai_cache_repository import AICacheRepository
from app.services.ai_usage_service import AIUsageService
from app.services.usage_budget import groq_requests_key, usage_budget


async def test_ai_usage_service_limits(monkeypatch):
    """Per-user and shared daily limits and the token budget are enforced before Groq is called."""
    monkeypatch.setattr(limits, "GROQ_DAILY_REQUESTS_PER_USER", 2)
    monkeypatch.setattr(limits, "GROQ_DAILY_REQUEST_LIMIT", 3)
    monkeypatch.setattr(limits, "GROQ_DAILY_TOKEN_BUDGET", 500)
    service = AIUsageService(Settings(GROQ_ENABLED=True, GROQ_API_KEY="mock-groq-key"))

    assert await service.can_make_request("user-abc") is True
    assert await service.can_make_request("user-abc") is True
    assert await service.can_make_request("user-abc") is False  # per-user cap (2)

    assert await service.can_make_request("user-xyz") is True  # 3rd shared request
    assert await service.can_make_request("user-new") is False  # shared cap (3)

    await service.record_usage("user-xyz", tokens_used=600)  # over the token budget
    assert await service.can_make_request("user-q") is False


async def test_ai_usage_is_off_without_key_or_flag():
    """With Groq disabled no request slot is ever spent."""
    service = AIUsageService(Settings(GROQ_ENABLED=False, GROQ_API_KEY=""))
    assert await service.can_make_request("user-abc") is False
    assert await usage_budget.store().get(groq_requests_key()) == 0


async def test_concurrent_ai_requests_never_exceed_shared_limit(monkeypatch):
    monkeypatch.setattr(limits, "GROQ_DAILY_REQUESTS_PER_USER", 100)
    monkeypatch.setattr(limits, "GROQ_DAILY_REQUEST_LIMIT", 7)
    service = AIUsageService(Settings(GROQ_ENABLED=True, GROQ_API_KEY="k"))
    results = await asyncio.gather(*(service.can_make_request(f"u{i}") for i in range(40)))
    assert sum(results) == 7


async def test_smart_layout_requires_login(client):
    payload = {
        "wall": {"width_inches": 120.0, "height_inches": 96.0},
        "frames": [{"item_id": "f1", "photo_width_inches": 12.0, "photo_height_inches": 16.0}],
        "engine_mode": "smart_llm",
    }
    for path in ("generate-layout", "redesign"):
        body = dict(payload, current_layout_style="grid") if path == "redesign" else payload
        res = await client.post(f"/api/v1/geometry/{path}", json=body)
        assert res.status_code == 401, path
    geometric = await client.post(
        "/api/v1/geometry/generate-layout", json=dict(payload, engine_mode="geometric")
    )
    assert geometric.status_code == 200  # the free geometry engine stays open


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
