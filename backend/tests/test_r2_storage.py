import pytest

from app.core.exceptions import ResourceNotFoundException, StorageUnavailableException
from tests.fakes import FakeR2Storage


@pytest.mark.asyncio
async def test_r2_storage_put_and_get():
    """Verify storing and retrieving objects from R2 storage."""
    r2 = FakeR2Storage()
    key = "users/123/photos/photo-1/thumbnail.webp"
    payload = b"RIFFfake_webp_bytes"

    saved_key = await r2.put_object(key, payload, "image/webp")
    assert saved_key == key

    data, c_type = await r2.get_object(key)
    assert data == payload
    assert c_type == "image/webp"


@pytest.mark.asyncio
async def test_r2_storage_get_missing_key_raises_404():
    """Verify accessing nonexistent R2 key raises ResourceNotFoundException."""
    r2 = FakeR2Storage()

    with pytest.raises(ResourceNotFoundException):
        await r2.get_object("users/123/nonexistent.webp")


@pytest.mark.asyncio
async def test_r2_storage_delete_objects():
    """Verify deleting objects from R2 storage."""
    r2 = FakeR2Storage()
    k1 = "k1.webp"
    k2 = "k2.webp"
    await r2.put_object(k1, b"1", "image/webp")
    await r2.put_object(k2, b"2", "image/webp")

    assert k1 in r2.objects
    assert k2 in r2.objects

    await r2.delete_objects([k1, k2])

    assert k1 not in r2.objects
    assert k2 not in r2.objects


@pytest.mark.asyncio
async def test_r2_storage_simulated_failure_raises_503():
    """Verify simulated network failure raises StorageUnavailableException."""
    r2 = FakeR2Storage()
    r2.should_fail_upload = True

    with pytest.raises(StorageUnavailableException):
        await r2.put_object("fail.webp", b"data", "image/webp")
