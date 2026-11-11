import pytest
from httpx import AsyncClient

from tests.fakes import FakePhotoRepository, FakeR2Storage
from tests.test_image_processing import make_test_image

_user_counter = 10000000


async def register_test_user(
    client: AsyncClient,
    email: str = "photouploader@example.com",
    phone: str | None = None,
) -> tuple[dict, str]:
    """Helper to register and obtain Bearer access token."""
    global _user_counter
    _user_counter += 1
    if not phone:
        phone = f"+919{_user_counter:09d}"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Photo Tester",
            "email": email,
            "phone": phone,
            "password": "SecurePassword123!",
        },
    )
    assert resp.status_code == 201, f"Register failed: {resp.status_code} {resp.text}"
    data = resp.json()
    return data["user"], data["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_upload_photo_success(
    client: AsyncClient,
    fake_photo_repo: FakePhotoRepository,
    fake_r2_storage: FakeR2Storage,
):
    """EP-PHOTO-01: Successfully upload JPEG image and verify R2 + DB persistence."""
    user, token = await register_test_user(client, "upload_success@example.com")
    raw_img = make_test_image(width=600, height=800, fmt="JPEG")

    response = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("diwali-portrait.jpg", raw_img, "image/jpeg")},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["user_id"] == user["id"]
    assert data["original_filename"] == "diwali-portrait.jpg"
    assert data["width_px"] == 600
    assert data["height_px"] == 800
    assert data["aspect_ratio"] == 0.75
    assert data["suggested_orientation"] == "portrait"
    assert data["mime_type"] == "image/jpeg"
    assert "sig=" in data["thumbnail_url"]
    assert "sig=" in data["preview_url"]

    photo_id = data["id"]

    # Verify MongoDB persistence
    db_photo = await fake_photo_repo.get_by_id(photo_id)
    assert db_photo is not None
    assert db_photo.width_px == 600
    assert db_photo.is_deleted is False

    # Verify Cloudflare R2 artifacts (original, preview, thumbnail)
    assert db_photo.storage_key in fake_r2_storage.objects
    assert db_photo.preview_key in fake_r2_storage.objects
    assert db_photo.thumbnail_key in fake_r2_storage.objects


@pytest.mark.asyncio
async def test_upload_unauthenticated_returns_401(client: AsyncClient):
    """EP-PHOTO-01: Unauthenticated upload returns 401 Unauthorized."""
    raw_img = make_test_image(width=400, height=400, fmt="JPEG")

    response = await client.post(
        "/api/v1/photos/upload",
        files={"file": ("test.jpg", raw_img, "image/jpeg")},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_upload_invalid_file_signature_returns_422(client: AsyncClient):
    """EP-PHOTO-01: Spoofed text file rejected with 422."""
    _, token = await register_test_user(client, "spoof@example.com")
    fake_file = b"This is text posing as a JPEG."

    response = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malicious.jpg", fake_file, "image/jpeg")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_upload_sub_300px_returns_422(client: AsyncClient):
    """EP-PHOTO-01: Low resolution image (< 300px) rejected with 422."""
    _, token = await register_test_user(client, "tiny@example.com")
    tiny_img = make_test_image(width=200, height=200, fmt="JPEG")

    response = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("tiny.jpg", tiny_img, "image/jpeg")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_upload_r2_failure_cleans_up_and_returns_503(
    client: AsyncClient,
    fake_r2_storage: FakeR2Storage,
    fake_photo_repo: FakePhotoRepository,
):
    """EP-PHOTO-01: R2 network failure cleans up orphaned objects and returns 503."""
    _, token = await register_test_user(client, "r2fail@example.com")
    raw_img = make_test_image(width=500, height=500, fmt="JPEG")

    fake_r2_storage.should_fail_upload = True

    response = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("fail.jpg", raw_img, "image/jpeg")},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_UNAVAILABLE"
    # Ensure no orphan metadata in database
    assert len(fake_photo_repo.photos) == 0


@pytest.mark.asyncio
async def test_upload_rate_limiting_exceeded(client: AsyncClient):
    """EP-PHOTO-01: Exceeding hourly upload limit returns 429."""
    _, token = await register_test_user(client, "spam@example.com")
    raw_img = make_test_image(width=350, height=350, fmt="JPEG")

    # Upload 30 allowed photos
    for i in range(30):
        resp = await client.post(
            "/api/v1/photos/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (f"p{i}.jpg", raw_img, "image/jpeg")},
        )
        assert resp.status_code == 201

    # 31st upload must be rate-limited
    blocked_resp = await client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("blocked.jpg", raw_img, "image/jpeg")},
    )

    assert blocked_resp.status_code == 429
    assert blocked_resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
