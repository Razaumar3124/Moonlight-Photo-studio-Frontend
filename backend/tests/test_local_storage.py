"""Development storage backend (STORAGE_BACKEND=local): safety, R2 parity and API flows."""

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient

from app.api.dependencies import get_storage
from app.core.config import Settings
from app.core.exceptions import ResourceNotFoundException
from app.storage import ObjectStorage, create_storage
from app.storage.local_storage import InvalidStorageKeyError, LocalStorage
from app.storage.r2_storage import R2Storage
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user


@pytest.fixture
def local_storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(root=tmp_path / "objects")


@pytest.fixture
def local_app(app, local_storage: LocalStorage):
    """The test app with the real local backend instead of the in-memory fake."""
    app.dependency_overrides[get_storage] = lambda: local_storage
    return app


def _split(url: str) -> tuple[str, int, str]:
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    return parts.path, int(query["exp"][0]), query["sig"][0]


# --------------------------------------------------------------------- backend


async def test_round_trip_preserves_bytes_and_content_type(local_storage: LocalStorage):
    key = "users/u1/photos/p1/thumbnail.webp"
    assert await local_storage.put_object(key, b"img-bytes", "image/webp", {"user_id": "u1"})

    data, content_type = await local_storage.get_object(key)
    assert data == b"img-bytes"
    assert content_type == "image/webp"
    assert (local_storage.root / "users/u1/photos/p1/thumbnail.webp").is_file()


async def test_overwrite_is_atomic_and_leaves_no_temp_files(local_storage: LocalStorage):
    key = "quotes/u1/MQ-2026-0001/preview.png"
    await local_storage.put_object(key, b"v1", "image/png")
    await local_storage.put_object(key, b"v2", "image/png")

    assert (await local_storage.get_object(key))[0] == b"v2"
    leftovers = [p.name for p in local_storage.root.rglob("*") if p.name.startswith(".tmp-")]
    assert leftovers == []


@pytest.mark.parametrize(
    "key",
    [
        "",
        "../escape.txt",
        "users/../../escape.txt",
        "/etc/passwd",
        "C:/Windows/win.ini",
        "users\\u1\\x.png",
        "users//x.png",
        "users/./x.png",
        "users/x.png.meta.json",
        "users/<script>.png",
        "a" * 600,
    ],
)
async def test_unsafe_keys_are_rejected(local_storage: LocalStorage, key: str):
    with pytest.raises(InvalidStorageKeyError):
        await local_storage.put_object(key, b"x", "image/png")
    with pytest.raises(ResourceNotFoundException):
        await local_storage.get_object(key)
    assert await local_storage.delete_object(key) is False
    assert not (local_storage.root.parent / "escape.txt").exists()


async def test_missing_object_is_not_found(local_storage: LocalStorage):
    with pytest.raises(ResourceNotFoundException):
        await local_storage.get_object("users/nobody/photo.png")


async def test_delete_removes_object_and_metadata(local_storage: LocalStorage):
    keys = ["users/u1/a.png", "users/u1/b.png"]
    for key in keys:
        await local_storage.put_object(key, b"x", "image/png")

    assert await local_storage.delete_object(keys[0]) is True
    assert await local_storage.delete_object(keys[0]) is False
    await local_storage.delete_objects(keys)

    assert [p for p in local_storage.root.rglob("*") if p.is_file()] == []


async def test_ping_creates_root_and_reports_latency(local_storage: LocalStorage):
    assert not local_storage.root.exists()
    latency = await local_storage.ping()
    assert latency >= 0
    assert local_storage.root.is_dir()
    assert local_storage.bucket_name == "local"


async def test_presigned_url_signature_rules(local_storage: LocalStorage):
    key = "quotes/u1/MQ-2026-0002/preview.png"
    path, exp, sig = _split(await local_storage.generate_presigned_url(key))

    assert path == f"/api/v1/storage/local/{key}"
    assert local_storage.verify_signature(key, exp, sig) is True
    assert local_storage.verify_signature(key, exp, "0" * 64) is False
    assert local_storage.verify_signature("quotes/u2/other.png", exp, sig) is False
    assert local_storage.verify_signature(key, exp + 1, sig) is False
    assert local_storage.verify_signature(key, 1, sig) is False  # expired


def test_both_backends_satisfy_the_storage_protocol(tmp_path: Path):
    assert isinstance(LocalStorage(tmp_path), ObjectStorage)
    assert isinstance(R2Storage(), ObjectStorage)


def test_factory_selects_backend(tmp_path: Path):
    local = create_storage(Settings(STORAGE_BACKEND="local", LOCAL_STORAGE_PATH=str(tmp_path)))
    assert isinstance(local, LocalStorage)
    assert local.root == tmp_path.resolve()

    # Constructing the R2 client is lazy: no network or credentials needed here.
    assert isinstance(create_storage(Settings(STORAGE_BACKEND="r2")), R2Storage)


# ------------------------------------------------------------- signed download


async def test_signed_download_endpoint_serves_object(
    local_app, client: AsyncClient, local_storage: LocalStorage
):
    key = "quotes/u1/MQ-2026-0003/preview.png"
    await local_storage.put_object(key, b"\x89PNG-data", "image/png")

    response = await client.get(await local_storage.generate_presigned_url(key))
    assert response.status_code == 200
    assert response.content == b"\x89PNG-data"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_signed_download_rejects_tampering(
    local_app, client: AsyncClient, local_storage: LocalStorage
):
    key = "quotes/u1/MQ-2026-0004/preview.png"
    await local_storage.put_object(key, b"secret", "image/png")
    path, exp, sig = _split(await local_storage.generate_presigned_url(key))

    tampered = await client.get(path, params={"exp": exp, "sig": "f" * 64})
    other_key = await client.get(
        "/api/v1/storage/local/quotes/u2/x.png", params={"exp": exp, "sig": sig}
    )
    traversal = await client.get(
        "/api/v1/storage/local/../../app/main.py", params={"exp": exp, "sig": sig}
    )
    unsigned = await client.get(path)

    assert tampered.status_code == 404
    assert other_key.status_code == 404
    assert traversal.status_code == 404
    assert unsigned.status_code == 422
    assert b"secret" not in tampered.content + other_key.content


async def test_signed_download_is_disabled_for_r2(client: AsyncClient):
    """With the R2 (fake) backend active the route always 404s."""
    response = await client.get(
        "/api/v1/storage/local/quotes/u1/x.png", params={"exp": 9999999999, "sig": "a" * 64}
    )
    assert response.status_code == 404


# ---------------------------------------------------------------- photo flow


async def test_photo_upload_view_delete_with_local_storage(
    local_app, client: AsyncClient, local_storage: LocalStorage
):
    """End-to-end: upload writes 3 files, the signed thumbnail URL loads, delete removes them."""
    _, token = await register_test_user(client, "local.storage@example.com")
    auth = {"Authorization": f"Bearer {token}"}

    upload = await client.post(
        "/api/v1/photos/upload",
        headers=auth,
        files={"file": ("wall.jpg", make_test_image(640, 480, fmt="JPEG"), "image/jpeg")},
    )
    assert upload.status_code == 201, upload.text
    photo = upload.json()
    stored = sorted(
        p.name for p in local_storage.root.rglob("*") if p.is_file() and "meta" not in p.name
    )
    assert stored == ["original.jpg", "preview.webp", "thumbnail.webp"]

    # Signed URL works without the Bearer header, like an <img src>.
    thumb = await client.get(photo["thumbnail_url"])
    assert thumb.status_code == 200
    assert thumb.content[:4] == b"RIFF"

    deleted = await client.delete(f"/api/v1/photos/{photo['id']}", headers=auth)
    assert deleted.status_code == 204
    assert [p for p in local_storage.root.rglob("*") if p.is_file()] == []
