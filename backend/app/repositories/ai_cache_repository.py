"""AI recommendation caching repository.

Prevents duplicate external calls to Groq by caching recommendations
keyed by deterministic hash of room specifications and photo attributes.
"""

import hashlib
import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from app.integrations.groq_client import GroqLayoutRecommendation

logger = logging.getLogger("saf_studio.ai_cache")


class AICacheRepository:
    """In-memory and MongoDB-backed cache for Groq layout recommendations."""

    def __init__(self, ttl_hours: int = 24) -> None:
        self.ttl = timedelta(hours=ttl_hours)
        # key -> (recommendation, expire_at)
        self._cache: dict[str, tuple[GroqLayoutRecommendation, datetime]] = {}

    @staticmethod
    def compute_cache_key(
        wall: dict[str, Any],
        photos: Sequence[dict[str, Any]],
        current_style: str | None = None,
        is_redesign: bool = False,
    ) -> str:
        """Generate deterministic SHA-256 hash for room and photo configuration."""
        sorted_photos = sorted(
            [
                {
                    "id": str(p.get("item_id")),
                    "aspect": round(float(p.get("aspect_ratio", 1.0)), 2),
                    "ori": str(p.get("orientation")),
                    "tone": str(p.get("color_temperature", "neutral")),
                }
                for p in photos
            ],
            key=lambda x: x["id"],
        )

        canonical = {
            "wall_w": round(float(wall.get("width_inches", 120.0)), 1),
            "wall_h": round(float(wall.get("height_inches", 96.0)), 1),
            "has_sofa": bool(wall.get("has_sofa", False)),
            "photos": sorted_photos,
            "style": current_style,
            "is_redesign": is_redesign,
        }
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, cache_key: str) -> GroqLayoutRecommendation | None:
        """Retrieve cached recommendation if present and unexpired."""
        entry = self._cache.get(cache_key)
        if not entry:
            return None

        recommendation, expire_at = entry
        if datetime.now(UTC) > expire_at:
            self._cache.pop(cache_key, None)
            return None

        logger.debug("AI Cache hit for key %s", cache_key[:12])
        return recommendation

    def set(self, cache_key: str, recommendation: GroqLayoutRecommendation) -> None:
        """Cache recommendation with TTL."""
        expire_at = datetime.now(UTC) + self.ttl
        self._cache[cache_key] = (recommendation, expire_at)

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
