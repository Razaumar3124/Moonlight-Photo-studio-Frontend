"""Unit and integration tests for POST /api/v1/quotes/prepare endpoint."""

import json
import urllib.parse

import pytest
from httpx import AsyncClient

from tests.fakes import FakeQuoteRepository, FakeR2Storage
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user


def make_valid_design_payload(frames_count: int = 9, style: str = "grid") -> dict:
    """Helper to construct valid Memory Wall planner state payload."""
    frames = []
    for i in range(1, frames_count + 1):
        frames.append(
            {
                "id": f"f_{i}",
                "sizeId": "12x16",
                "orientation": "portrait" if i % 2 == 1 else "landscape",
                "finishId": "natural-oak",
                "mount": {
                    "enabled": True,
                    "colourId": "museum-white",
                    "marginIn": 2.0,
                },
                "photo": {
                    "kind": "sample",
                    "sampleId": f"frame-{i}",
                    "name": f"Family Photo {i}",
                },
                "x": 10.0 * i,
                "y": 15.0,
            }
        )

    return {
        "title": "Living Room Gallery Wall",
        "wall": {
            "widthIn": 120.0,
            "heightIn": 96.0,
            "paintId": "warm-chalk",
            "colorHex": "#F0EBE4",
            "displayUnit": "in",
            "hasSofa": True,
        },
        "layout": {
            "style": style,
            "gapIn": 2.0,
        },
        "frames": frames,
    }


@pytest.mark.asyncio
async def test_quote_prepare_success(
    client: AsyncClient,
    fake_quote_repo: FakeQuoteRepository,
    fake_r2_storage: FakeR2Storage,
):
    """POST /api/v1/quotes/prepare creates quote, uploads preview, and returns WhatsApp URL."""
    user, token = await register_test_user(
        client, email="quote_customer@example.com", phone="+919876543210"
    )

    design_payload = make_valid_design_payload(frames_count=9, style="grid")
    preview_bytes = make_test_image(width=1200, height=800, fmt="PNG")

    response = await client.post(
        "/api/v1/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(design_payload)},
        files={"file": ("preview.png", preview_bytes, "image/png")},
    )

    assert response.status_code == 201, f"Failed: {response.status_code} {response.text}"
    data = response.json()

    assert "quote_id" in data
    quote_ref = data["quote_id"]
    assert quote_ref.startswith("SQ-")
    assert data["status"] == "draft"
    assert "whatsapp_url" in data
    assert "report_url" in data
    assert "expires_at" in data

    # Verify WhatsApp Click-to-Chat URL structure
    wa_url = data["whatsapp_url"]
    assert wa_url.startswith("https://wa.me/919876543210?text=")

    encoded_text = wa_url.split("?text=")[1]
    decoded_text = urllib.parse.unquote(encoded_text)

    assert "Hello SAF Studio! 👋" in decoded_text
    assert f"Reference: {quote_ref}" in decoded_text
    assert "120 × 96 inches" in decoded_text
    assert "Gallery Grid" in decoded_text
    assert "Frames: 9" in decoded_text
    assert "Natural Oak" in decoded_text
    assert data["report_url"] in decoded_text
    assert f"Name: {user['full_name']}" in decoded_text
    assert "Mobile: +919876543210" in decoded_text

    # Verify persistence in MongoDB fake repository
    db_quote = await fake_quote_repo.get_by_reference(quote_ref)
    assert db_quote is not None
    assert str(db_quote.user_id) == str(user["id"])
    assert db_quote.customer.full_name == user["full_name"]
    assert db_quote.customer.email == user["email"]
    assert db_quote.customer.phone == user["phone"]
    assert len(db_quote.frames) == 9

    # Verify R2 upload
    preview_key = db_quote.preview_image_key
    assert preview_key in fake_r2_storage.objects
    uploaded_bytes, content_type, _ = fake_r2_storage.objects[preview_key]
    assert content_type == "image/png"
    assert len(uploaded_bytes) == len(preview_bytes)


@pytest.mark.asyncio
async def test_quote_prepare_unauthenticated_returns_401(client: AsyncClient):
    """POST /api/v1/quotes/prepare without authentication returns 401."""
    design_payload = make_valid_design_payload(frames_count=4)
    preview_bytes = make_test_image(width=800, height=600, fmt="PNG")

    response = await client.post(
        "/api/v1/quotes/prepare",
        data={"design_data": json.dumps(design_payload)},
        files={"file": ("preview.png", preview_bytes, "image/png")},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_quote_prepare_invalid_wall_dimensions_returns_422(client: AsyncClient):
    """POST /api/v1/quotes/prepare with negative wall size returns 422."""
    _, token = await register_test_user(client, email="invalid_wall@example.com")

    design_payload = make_valid_design_payload(frames_count=3)
    design_payload["wall"]["widthIn"] = -50.0  # Invalid!
    preview_bytes = make_test_image(width=800, height=600, fmt="PNG")

    response = await client.post(
        "/api/v1/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(design_payload)},
        files={"file": ("preview.png", preview_bytes, "image/png")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_quote_prepare_empty_frames_returns_422(client: AsyncClient):
    """POST /api/v1/quotes/prepare with 0 frames returns 422."""
    _, token = await register_test_user(client, email="empty_frames@example.com")

    design_payload = make_valid_design_payload(frames_count=0)
    design_payload["frames"] = []
    preview_bytes = make_test_image(width=800, height=600, fmt="PNG")

    response = await client.post(
        "/api/v1/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(design_payload)},
        files={"file": ("preview.png", preview_bytes, "image/png")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_quote_prepare_corrupt_preview_image_returns_422(client: AsyncClient):
    """POST /api/v1/quotes/prepare with invalid image bytes returns 422."""
    _, token = await register_test_user(client, email="corrupt_preview@example.com")

    design_payload = make_valid_design_payload(frames_count=3)
    garbage_bytes = b"This is not a real image header"

    response = await client.post(
        "/api/v1/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(design_payload)},
        files={"file": ("preview.png", garbage_bytes, "image/png")},
    )
    assert response.status_code == 422
    assert (
        "Preview image must be a valid" in response.text or "unsupported" in response.text.lower()
    )
