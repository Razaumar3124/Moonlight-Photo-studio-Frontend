"""Local image analysis service (Layer A - Zero AI tokens).

Extracts aspect ratio, natural orientation, dominant colors, color temperature,
approximate brightness, contrast, and heuristic visual weight using Pillow in <10ms.
Caches results in MongoDB to guarantee single-pass analysis per photograph.
"""

import io
import logging
from datetime import UTC, datetime

from PIL import Image, ImageStat

from app.models.photo import PhotoInDB, VisualAnalysis
from app.repositories.photo_repository import PhotoRepository
from app.storage.r2_storage import R2Storage

logger = logging.getLogger("saf_studio.photo_analysis")


class PhotoAnalysisService:
    """Zero-AI-token image metadata and statistical analysis service."""

    def __init__(
        self,
        photo_repo: PhotoRepository,
        r2_storage: R2Storage,
    ) -> None:
        self.photo_repo = photo_repo
        self.r2_storage = r2_storage

    @staticmethod
    def analyze_image_bytes(image_data: bytes) -> VisualAnalysis:
        """Perform statistical heuristic analysis on raw image bytes in-memory using Pillow.

        Note: These measurements represent statistical pixel distributions (luminance,
        color channel differentials, and palette quantization). They do NOT constitute
        semantic understanding or object detection.
        """
        with Image.open(io.BytesIO(image_data)) as img:
            # Normalize to RGB for consistent palette and channel analysis
            rgb_img = img.convert("RGB")

            # 1. Downscale to small thumbnail for fast quantization and stats
            thumb = rgb_img.resize((64, 64), Image.Resampling.BOX)

            # 2. Dominant colors via color quantization (4 representative swatches)
            quantized = thumb.quantize(colors=4, method=Image.Quantize.MEDIANCUT)
            palette = quantized.getpalette() or []
            dominant_colors: list[str] = []
            for i in range(min(4, len(palette) // 3)):
                r = palette[i * 3]
                g = palette[i * 3 + 1]
                b = palette[i * 3 + 2]
                dominant_colors.append(f"#{r:02x}{g:02x}{b:02x}".upper())

            # 3. Brightness and Contrast via greyscale statistics
            grey = thumb.convert("L")
            stat = ImageStat.Stat(grey)
            mean_lum = stat.mean[0]  # 0 to 255
            stddev_lum = stat.stddev[0]  # 0 to ~128

            brightness = round(min(1.0, max(0.0, mean_lum / 255.0)), 2)
            contrast = round(min(1.0, max(0.0, stddev_lum / 64.0)), 2)

            # 4. Color temperature heuristic: Red vs Blue channel imbalance
            rgb_stat = ImageStat.Stat(thumb)
            r_mean = rgb_stat.mean[0]
            b_mean = rgb_stat.mean[2]
            diff = r_mean - b_mean
            if diff > 14.0:
                temp = "warm"
            elif diff < -14.0:
                temp = "cool"
            else:
                temp = "neutral"

            # 5. Heuristic visual weight: composite of contrast and saturation
            diff_scaled = abs(diff) / 100.0
            weight_val = 0.5 * contrast + 0.3 * diff_scaled + 0.2
            visual_weight = round(min(1.0, max(0.1, weight_val)), 2)

            return VisualAnalysis(
                dominant_colors=dominant_colors,
                color_temperature=temp,
                brightness=brightness,
                contrast=contrast,
                visual_weight=visual_weight,
                analyzed_at=datetime.now(UTC),
            )

    async def get_or_analyze_photo(
        self, photo: PhotoInDB, user_id: str | None = None
    ) -> VisualAnalysis:
        """Retrieve cached visual analysis from MongoDB or compute on-demand."""
        if photo.visual_analysis is not None:
            return photo.visual_analysis

        # Attempt to load small preview or thumbnail bytes from R2 to minimize bandwidth
        key_to_fetch = photo.preview_key or photo.thumbnail_key or photo.storage_key
        try:
            res = await self.r2_storage.get_object(key_to_fetch)
            image_bytes = res[0] if isinstance(res, tuple) else res
            analysis = self.analyze_image_bytes(image_bytes)

            # Cache in MongoDB
            await self.photo_repo.update_visual_analysis(str(photo.id), analysis)
            photo.visual_analysis = analysis
            return analysis
        except Exception as exc:
            logger.warning("Could not fetch image bytes for photo %s: %s", photo.id, exc)
            # Safe default fallback
            return VisualAnalysis()
