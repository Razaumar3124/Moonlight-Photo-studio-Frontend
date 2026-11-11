import io

import pytest
from bson import ObjectId
from PIL import Image

from app.models.photo import PhotoInDB
from app.services.photo_analysis_service import PhotoAnalysisService
from tests.fakes import FakePhotoRepository, FakeR2Storage


def create_test_image_bytes(
    width: int = 400,
    height: int = 300,
    color: tuple[int, int, int] = (200, 100, 50),
) -> bytes:
    """Generate RGB image in JPEG format in-memory."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_analyze_image_bytes_statistical_extraction():
    """Layer A: Statistical extraction returns valid colors, luminance, contrast and weight."""
    # Warm reddish-orange image (R: 220, G: 80, B: 30)
    warm_bytes = create_test_image_bytes(color=(220, 80, 30))
    analysis = PhotoAnalysisService.analyze_image_bytes(warm_bytes)

    assert len(analysis.dominant_colors) > 0
    assert analysis.dominant_colors[0].startswith("#")
    assert analysis.color_temperature == "warm"
    assert 0.0 <= analysis.brightness <= 1.0
    assert 0.0 <= analysis.contrast <= 1.0
    assert 0.0 <= analysis.visual_weight <= 1.0


def test_analyze_image_bytes_cool_temperature():
    """Cool blue image is categorized as cool temperature."""
    cool_bytes = create_test_image_bytes(color=(40, 80, 210))
    analysis = PhotoAnalysisService.analyze_image_bytes(cool_bytes)
    assert analysis.color_temperature == "cool"


@pytest.mark.asyncio
async def test_get_or_analyze_photo_caching():
    """Photo is analyzed once and cached in MongoDB for zero redundant processing."""
    fake_repo = FakePhotoRepository()
    fake_r2 = FakeR2Storage()
    service = PhotoAnalysisService(photo_repo=fake_repo, r2_storage=fake_r2)

    # Store fake image in R2
    img_bytes = create_test_image_bytes(color=(150, 150, 150))
    await fake_r2.put_object("preview-key.jpg", img_bytes, "image/jpeg")

    # Create photo without visual_analysis
    valid_user_id = str(ObjectId())
    photo = PhotoInDB(
        user_id=valid_user_id,
        original_filename="sample.jpg",
        storage_key="orig.jpg",
        thumbnail_key="thumb.jpg",
        preview_key="preview-key.jpg",
        bucket="saf-bucket",
        mime_type="image/jpeg",
        file_size_bytes=len(img_bytes),
        width_px=400,
        height_px=300,
        aspect_ratio=1.3333,
        suggested_orientation="landscape",
    )
    await fake_repo.create(photo)

    # 1st call computes and caches in repo
    res1 = await service.get_or_analyze_photo(photo)
    assert res1.brightness > 0
    assert photo.visual_analysis is not None

    # Verify document in repo now has visual_analysis
    db_doc = await fake_repo.get_by_id(str(photo.id))
    assert db_doc.visual_analysis is not None
    assert db_doc.visual_analysis.dominant_colors == res1.dominant_colors

    # 2nd call reuses cached visual_analysis directly without accessing R2
    res2 = await service.get_or_analyze_photo(photo)
    assert res2.dominant_colors == res1.dominant_colors
