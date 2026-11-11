"""Unit and integration tests for digital design reports and share endpoints."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.security import hash_token
from app.models.quote import (
    QuoteContactSnapshot,
    QuoteInDB,
    QuoteWallSnapshot,
)
from tests.fakes import FakeQuoteRepository, FakeR2Storage
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user
from tests.test_quote_prepare import make_valid_design_payload


@pytest.fixture
async def sample_quote(
    client: AsyncClient,
    fake_quote_repo: FakeQuoteRepository,
    fake_r2_storage: FakeR2Storage,
) -> tuple[dict, str, QuoteInDB, str]:
    """Helper fixture to create a valid prepared quote with share token."""
    user, token = await register_test_user(
        client, email="report_viewer@example.com", phone="+919876543210"
    )

    design_payload = make_valid_design_payload(frames_count=6, style="salon")
    preview_bytes = make_test_image(width=1200, height=800, fmt="PNG")

    resp = await client.post(
        "/api/v1/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(design_payload)},
        files={"file": ("preview.png", preview_bytes, "image/png")},
    )
    assert resp.status_code == 201
    data = resp.json()

    # Extract raw share token from report_url
    raw_token = data["report_url"].split("/q/")[1]
    quote = await fake_quote_repo.get_by_reference(data["quote_id"])
    assert quote is not None

    return user, token, quote, raw_token


@pytest.mark.asyncio
async def test_get_shared_report_html_default(
    client: AsyncClient,
    sample_quote: tuple[dict, str, QuoteInDB, str],
):
    """GET /api/v1/quotes/share/{token} returns 200 with responsive, branded HTML."""
    user, token, quote, raw_token = sample_quote

    response = await client.get(f"/api/v1/quotes/share/{raw_token}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    html = response.text

    # SAF Studio branding
    assert "SAF Studio" in html
    assert "Bespoke Gallery Framing" in html

    # Quote reference and design metadata
    assert quote.quote_reference in html
    assert "Salon Arrangement" in html
    assert "6 Frames" in html
    assert "120 × 96 inches" in html

    # Preview image tag pointing to streaming preview route
    assert f"/quotes/share/{raw_token}/preview" in html

    # Customer info (masked)
    assert user["full_name"] in html
    assert "••••" in html

    # Frame specifications table
    assert "Frame-by-Frame Specifications" in html
    assert "Natural Oak" in html

    # Strict check: No pricing or tax calculations allowed in digital design report
    assert "₹" not in html
    assert "INR" not in html
    assert "GST" not in html
    assert "Shipping Fee" not in html
    assert "Subtotal" not in html
    assert "Total Estimated" not in html


@pytest.mark.asyncio
async def test_get_shared_report_json_format(
    client: AsyncClient,
    sample_quote: tuple[dict, str, QuoteInDB, str],
):
    """GET /api/v1/quotes/share/{token} with Accept: application/json returns QuoteShareResponse."""
    user, token, quote, raw_token = sample_quote

    response = await client.get(
        f"/api/v1/quotes/share/{raw_token}",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]

    data = response.json()
    assert data["quote_id"] == quote.quote_reference
    assert data["customer_name"] == user["full_name"]
    assert "••••" in data["customer_contact_masked"]
    assert data["frame_count"] == 6
    assert data["layout_style"] == "Salon Arrangement"
    assert "preview_image_url" in data
    assert len(data["frames"]) == 6


@pytest.mark.asyncio
async def test_get_shared_preview_image_stream(
    client: AsyncClient,
    sample_quote: tuple[dict, str, QuoteInDB, str],
    fake_r2_storage: FakeR2Storage,
):
    """GET /api/v1/quotes/share/{token}/preview streams preview image from R2 without auth."""
    user, token, quote, raw_token = sample_quote

    response = await client.get(f"/api/v1/quotes/share/{raw_token}/preview")
    assert response.status_code == 200
    assert "image/png" in response.headers["content-type"]
    assert "public, max-age=" in response.headers["cache-control"]
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_get_shared_report_invalid_token_returns_404(client: AsyncClient):
    """GET /api/v1/quotes/share/{token} with invalid token returns 404."""
    response = await client.get("/api/v1/quotes/share/nonexistent_fake_token_12345")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_shared_report_expired_token_returns_404(
    client: AsyncClient,
    fake_quote_repo: FakeQuoteRepository,
    fake_r2_storage: FakeR2Storage,
):
    """GET /api/v1/quotes/share/{token} with expired quote returns 404."""
    raw_token = "expired_test_token_abcdef123456"
    token_hash = hash_token(raw_token)

    expired_quote = QuoteInDB(
        quote_reference="SQ-2025-0001",
        user_id="user_123",
        customer=QuoteContactSnapshot(
            full_name="Past User", email="past@example.com", phone="+919876543210"
        ),
        design_title="Old Wall",
        layout_style="grid",
        wall=QuoteWallSnapshot(width_inches=100.0, height_inches=80.0),
        preview_image_key="quotes/user_123/SQ-2025-0001/preview.png",
        share_token_hash=token_hash,
        share_token_prefix=raw_token[:8],
        status="draft",
        # Expired 10 days ago
        expires_at=datetime.now(UTC) - timedelta(days=10),
    )
    await fake_quote_repo.create(expired_quote)

    response = await client.get(f"/api/v1/quotes/share/{raw_token}")
    assert response.status_code == 404
    assert "expired" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_get_shared_report_with_naive_datetime(
    client: AsyncClient,
    sample_quote: tuple[dict, str, QuoteInDB, str],
    fake_quote_repo: FakeQuoteRepository,
):
    """Ensure report loading succeeds when MongoDB deserializes dates as offset-naive datetimes."""
    _, _, quote, raw_token = sample_quote
    # Strip tzinfo to simulate PyMongo BSON date deserialization
    naive_expiry = quote.expires_at.replace(tzinfo=None)
    fake_quote_repo.quotes[str(quote.id)]["expires_at"] = naive_expiry

    response = await client.get(f"/api/v1/quotes/share/{raw_token}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_redirect_root_share_url(
    client: AsyncClient,
    sample_quote: tuple[dict, str, QuoteInDB, str],
):
    """GET /q/{token} redirects 307 to /api/v1/quotes/share/{token}."""
    _, _, _, raw_token = sample_quote

    response = await client.get(f"/q/{raw_token}", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == f"/api/v1/quotes/share/{raw_token}"


@pytest.mark.asyncio
async def test_get_authorized_quote_by_id(
    client: AsyncClient,
    sample_quote: tuple[dict, str, QuoteInDB, str],
):
    """GET /api/v1/quotes/{id} returns full authorized quote specifications to owner."""
    user, token, quote, _ = sample_quote

    response = await client.get(
        f"/api/v1/quotes/{quote.quote_reference}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["quote_id"] == quote.quote_reference
    assert data["status"] == "draft"
    assert data["customer_name"] == user["full_name"]
    assert data["customer_email"] == user["email"]
    assert data["frame_count"] == 6
    assert len(data["frames"]) == 6
