"""Comprehensive security and fault-tolerance tests for quotes and design reports."""

import json

import pytest
from httpx import AsyncClient

from tests.fakes import FakePhotoRepository, FakeQuoteRepository, FakeR2Storage
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user
from tests.test_quote_prepare import make_valid_design_payload


@pytest.mark.asyncio
async def test_quote_security_cross_user_photo_idor_blocked(
    client: AsyncClient,
    fake_photo_repo: FakePhotoRepository,
    fake_r2_storage: FakeR2Storage,
):
    """BOLA / IDOR defense: User B cannot use User A's private uploaded photo in their quote."""
    # 1. User A uploads private photo
    user_a, token_a = await register_test_user(client, email="usera@example.com")
    raw_img = make_test_image(width=600, height=800, fmt="JPEG")
    upload_res = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("family-secret.jpg", raw_img, "image/jpeg")},
    )
    assert upload_res.status_code == 201
    photo_a_id = upload_res.json()["id"]

    # 2. User B attempts to prepare quote referencing User A's photo
    _, token_b = await register_test_user(client, email="userb@example.com")
    payload = make_valid_design_payload(frames_count=2)
    payload["frames"][0]["photo"] = {
        "kind": "upload",
        "photoId": photo_a_id,
        "name": "Stolen Photo",
    }
    preview_bytes = make_test_image(width=1000, height=800, fmt="PNG")

    response = await client.post(
        "/api/v1/quotes/prepare",
        headers={"Authorization": f"Bearer {token_b}"},
        data={"design_data": json.dumps(payload)},
        files={"file": ("preview.png", preview_bytes, "image/png")},
    )

    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "permission" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_quote_security_cross_user_quote_access_blocked(
    client: AsyncClient,
    fake_quote_repo: FakeQuoteRepository,
    fake_r2_storage: FakeR2Storage,
):
    """IDOR defense: User B cannot view User A's authorized quote record."""
    user_a, token_a = await register_test_user(client, email="owner_a@example.com")
    _, token_b = await register_test_user(client, email="intruder_b@example.com")

    payload = make_valid_design_payload(frames_count=3)
    preview_bytes = make_test_image(width=1000, height=800, fmt="PNG")

    res = await client.post(
        "/api/v1/quotes/prepare",
        headers={"Authorization": f"Bearer {token_a}"},
        data={"design_data": json.dumps(payload)},
        files={"file": ("preview.png", preview_bytes, "image/png")},
    )
    assert res.status_code == 201
    quote_id = res.json()["quote_id"]

    # User B attempts to access User A's quote
    forbidden_res = await client.get(
        f"/api/v1/quotes/{quote_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden_res.status_code == 404


@pytest.mark.asyncio
async def test_quote_rollback_on_database_failure(
    client: AsyncClient,
    fake_quote_repo: FakeQuoteRepository,
    fake_r2_storage: FakeR2Storage,
):
    """Partial failure safety: If MongoDB insert fails, R2 preview object is cleanly deleted."""
    user, token = await register_test_user(client, email="rollback_user@example.com")
    payload = make_valid_design_payload(frames_count=3)
    preview_bytes = make_test_image(width=1000, height=800, fmt="PNG")

    # Simulate MongoDB failure on insert
    fake_quote_repo.should_fail_create = True

    initial_r2_count = len(fake_r2_storage.objects)

    response = await client.post(
        "/api/v1/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(payload)},
        files={"file": ("preview.png", preview_bytes, "image/png")},
    )

    # Re-enable repository
    fake_quote_repo.should_fail_create = False

    assert response.status_code == 503
    # Verify no orphaned R2 objects were left behind
    assert len(fake_r2_storage.objects) == initial_r2_count


@pytest.mark.asyncio
async def test_quote_rate_limiting_exceeded(
    client: AsyncClient,
    fake_quote_repo: FakeQuoteRepository,
    fake_r2_storage: FakeR2Storage,
):
    """Enforces rate limiting on POST /api/v1/quotes/prepare."""
    user, token = await register_test_user(client, email="spammer@example.com")
    payload = make_valid_design_payload(frames_count=2)
    preview_bytes = make_test_image(width=800, height=600, fmt="PNG")

    # Limit is 10 requests per hour in settings
    for _ in range(10):
        res = await client.post(
            "/api/v1/quotes/prepare",
            headers={"Authorization": f"Bearer {token}"},
            data={"design_data": json.dumps(payload)},
            files={"file": ("preview.png", preview_bytes, "image/png")},
        )
        assert res.status_code == 201

    # 11th request must be rejected with 429
    blocked = await client.post(
        "/api/v1/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(payload)},
        files={"file": ("preview.png", preview_bytes, "image/png")},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_quote_html_xss_prevention(
    client: AsyncClient,
    fake_quote_repo: FakeQuoteRepository,
    fake_r2_storage: FakeR2Storage,
):
    """Jinja2 autoescaping prevents script injection via customer profile or design title."""
    user, token = await register_test_user(
        client,
        email="xss_test@example.com",
    )
    # Inject XSS payload in design title
    payload = make_valid_design_payload(frames_count=2)
    payload["title"] = "<script>alert('xss_attack')</script> Gallery"
    preview_bytes = make_test_image(width=800, height=600, fmt="PNG")

    res = await client.post(
        "/api/v1/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(payload)},
        files={"file": ("preview.png", preview_bytes, "image/png")},
    )
    assert res.status_code == 201
    raw_token = res.json()["report_url"].split("/q/")[1]

    # Retrieve report HTML
    html_res = await client.get(f"/api/v1/quotes/share/{raw_token}")
    assert html_res.status_code == 200
    html = html_res.text

    # Script tag must be escaped, never raw
    assert "<script>alert('xss_attack')</script>" not in html
    assert (
        "&lt;script&gt;alert(&#39;xss_attack&#39;)&lt;/script&gt;" in html
        or "&lt;script&gt;" in html
    )
