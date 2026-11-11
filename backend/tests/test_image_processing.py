import io

import pytest
from PIL import Image

from app.core.exceptions import ValidationException
from app.services.image_processing_service import ImageProcessingService


def make_test_image(
    width: int = 400,
    height: int = 300,
    fmt: str = "JPEG",
    color: str = "blue",
) -> bytes:
    """Helper to generate binary test image in memory."""
    buf = io.BytesIO()
    mode = "RGBA" if fmt.upper() == "PNG" else "RGB"
    img = Image.new(mode, (width, height), color=color)
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_process_valid_jpeg():
    """Verify JPEG image sniffing, processing, and WebP generation."""
    svc = ImageProcessingService()
    raw = make_test_image(width=800, height=600, fmt="JPEG")

    res = await svc.process_image(raw, declared_content_type="image/jpeg")

    assert res.mime_type == "image/jpeg"
    assert res.natural_width == 800
    assert res.natural_height == 600
    assert res.aspect_ratio == 1.3333
    assert res.suggested_orientation == "landscape"
    assert len(res.preview_bytes) > 0
    assert len(res.thumbnail_bytes) > 0

    # Verify thumbnail dimensions
    with Image.open(io.BytesIO(res.thumbnail_bytes)) as thumb:
        assert thumb.format == "WEBP"
        assert max(thumb.size) <= 300


@pytest.mark.asyncio
async def test_process_valid_png():
    """Verify PNG image processing."""
    svc = ImageProcessingService()
    raw = make_test_image(width=400, height=600, fmt="PNG")

    res = await svc.process_image(raw, declared_content_type="image/png")

    assert res.mime_type == "image/png"
    assert res.natural_width == 400
    assert res.natural_height == 600
    assert res.suggested_orientation == "portrait"


@pytest.mark.asyncio
async def test_process_valid_webp():
    """Verify WebP image processing."""
    svc = ImageProcessingService()
    raw = make_test_image(width=500, height=500, fmt="WEBP")

    res = await svc.process_image(raw, declared_content_type="image/webp")

    assert res.mime_type == "image/webp"
    assert res.natural_width == 500
    assert res.natural_height == 500
    assert res.suggested_orientation == "square"


@pytest.mark.asyncio
async def test_reject_unsupported_magic_bytes():
    """Verify non-image binary or text payload is rejected."""
    svc = ImageProcessingService()
    fake_bytes = b"Hello, this is a plain text file, not a real image header!"

    with pytest.raises(ValidationException) as exc:
        await svc.process_image(fake_bytes, declared_content_type="image/jpeg")

    assert "JPEG, PNG or WebP" in exc.value.message


@pytest.mark.asyncio
async def test_reject_sub_300px_dimension():
    """Verify images with shortest side < 300px are rejected."""
    svc = ImageProcessingService()
    too_small = make_test_image(width=250, height=400, fmt="JPEG")

    with pytest.raises(ValidationException) as exc:
        await svc.process_image(too_small)

    assert "too small to print well" in exc.value.message


@pytest.mark.asyncio
async def test_reject_oversized_payload():
    """Verify payloads exceeding configured upload size are rejected."""
    svc = ImageProcessingService()
    # 26 MB dummy payload
    huge_payload = b"\xff\xd8\xff" + b"\x00" * (26 * 1024 * 1024)

    with pytest.raises(ValidationException) as exc:
        await svc.process_image(huge_payload)

    assert "larger than" in exc.value.message
