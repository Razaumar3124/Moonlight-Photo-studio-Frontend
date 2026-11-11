import asyncio
import io
import logging
from dataclasses import dataclass

from PIL import Image, ImageOps

from app.core.config import get_settings
from app.core.exceptions import ValidationException

logger = logging.getLogger("saf_studio.image_processing")

# Guard against decompression bomb attacks (100 megapixels max)
Image.MAX_IMAGE_PIXELS = 100_000_000

# Magic byte signatures for supported photo formats
MAGIC_SIGNATURES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],  # With 'WEBP' at index 8
}


@dataclass
class ProcessedImageResult:
    """Output container for validated and processed image artifacts."""

    natural_width: int
    natural_height: int
    aspect_ratio: float
    suggested_orientation: str
    mime_type: str
    file_size_bytes: int
    original_bytes: bytes
    preview_bytes: bytes
    thumbnail_bytes: bytes


class ImageProcessingService:
    """Service handling image format sniffing, sanitization, EXIF rotation, and WebP generation."""

    @staticmethod
    def sniff_mime_type(data: bytes) -> str | None:
        """Inspect binary file headers to safely detect actual image MIME type."""
        if len(data) < 12:
            return None

        # Check JPEG
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"

        # Check PNG
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"

        # Check WebP (RIFF....WEBP)
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"

        return None

    def _sync_process(
        self,
        raw_bytes: bytes,
        declared_content_type: str | None = None,
    ) -> ProcessedImageResult:
        """Synchronous CPU-bound image verification, normalization, and optimization."""
        settings = get_settings()

        # 1. Enforce payload size limits
        file_size = len(raw_bytes)
        if file_size > settings.max_upload_bytes:
            max_mb = settings.R2_MAX_UPLOAD_MB
            raise ValidationException(
                message=f"That photo is larger than {max_mb} MB. Please choose a smaller file.",
                details=[
                    {
                        "field": "file",
                        "issue": f"File size ({file_size} bytes) exceeds {max_mb} MB limit",
                    }
                ],
            )

        # 2. Validate file signature / magic bytes
        sniffed_type = self.sniff_mime_type(raw_bytes)
        if not sniffed_type:
            raise ValidationException(
                message="Please choose a JPEG, PNG or WebP photo.",
                details=[
                    {
                        "field": "file",
                        "issue": (
                            "File signature does not match supported image "
                            "formats (JPEG, PNG, WebP)"
                        ),
                    }
                ],
            )

        # 3. Open image with Pillow and verify structural integrity
        try:
            with Image.open(io.BytesIO(raw_bytes)) as probe:
                probe.verify()
        except Exception as exc:
            logger.warning("Pillow verify failed: %s", exc)
            raise ValidationException(
                message=(
                    "We couldn’t read that image. It may be damaged or in an unsupported format."
                ),
                details=[{"field": "file", "issue": f"Image stream is corrupt: {exc}"}],
            ) from exc

        # 4. Re-open for transformation (after verify() the image descriptor is exhausted)
        try:
            img = Image.open(io.BytesIO(raw_bytes))
        except Exception as exc:
            raise ValidationException(
                message="We couldn’t read that image.",
                details=[{"field": "file", "issue": str(exc)}],
            ) from exc

        # 5. Apply EXIF orientation transpose (smartphone cameras, portrait modes)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception as exc:
            logger.debug("EXIF transpose skipped or failed: %s", exc)

        # 6. Check natural dimensions
        width, height = img.size
        min_side = min(width, height)
        if min_side < settings.PHOTO_MIN_SIDE_PX:
            raise ValidationException(
                message=(
                    "That photo is too small to print well "
                    f"(under {settings.PHOTO_MIN_SIDE_PX} px)."
                ),
                details=[
                    {
                        "field": "file",
                        "issue": (
                            f"Shortest side {min_side}px is below "
                            f"minimum {settings.PHOTO_MIN_SIDE_PX}px"
                        ),
                    }
                ],
            )

        if width > settings.PHOTO_MAX_WIDTH_PX or height > settings.PHOTO_MAX_HEIGHT_PX:
            raise ValidationException(
                message=(
                    f"Image resolution {width}x{height} exceeds the maximum allowed limit "
                    f"of {settings.PHOTO_MAX_WIDTH_PX}x{settings.PHOTO_MAX_HEIGHT_PX} pixels."
                ),
                details=[{"field": "file", "issue": "Resolution exceeds maximum allowed bounds"}],
            )

        # 7. Calculate aspect ratio and orientation
        aspect_ratio = round(width / height, 4)
        if width > height:
            orientation = "landscape"
        elif height > width:
            orientation = "portrait"
        else:
            orientation = "square"

        # Normalize color mode for WebP compatibility
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "transparency" in img.info else "RGB")

        # 8. Generate 300px thumbnail (WebP, quality=80)
        thumb = img.copy()
        thumb.thumbnail((300, 300), Image.Resampling.LANCZOS)
        thumb_buffer = io.BytesIO()
        thumb.save(thumb_buffer, format="WEBP", quality=80, method=4)
        thumb_bytes = thumb_buffer.getvalue()

        # 9. Generate 1600px preview (WebP, quality=85)
        prev = img.copy()
        prev.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        prev_buffer = io.BytesIO()
        prev.save(prev_buffer, format="WEBP", quality=85, method=4)
        prev_bytes = prev_buffer.getvalue()

        return ProcessedImageResult(
            natural_width=width,
            natural_height=height,
            aspect_ratio=aspect_ratio,
            suggested_orientation=orientation,
            mime_type=sniffed_type,
            file_size_bytes=file_size,
            original_bytes=raw_bytes,
            preview_bytes=prev_bytes,
            thumbnail_bytes=thumb_bytes,
        )

    async def process_image(
        self,
        raw_bytes: bytes,
        declared_content_type: str | None = None,
    ) -> ProcessedImageResult:
        """Asynchronously process an image in a worker threadpool."""
        return await asyncio.to_thread(
            self._sync_process,
            raw_bytes,
            declared_content_type,
        )
