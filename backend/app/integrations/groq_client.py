"""Groq AI Cloud Inference Client (Layer B - Semantic Layout Curator).

Sends compact JSON metadata (<200 tokens) to Groq text LLMs (e.g. Llama-3.3-70B)
to obtain high-level compositional recommendations (style, focal anchor, photo ordering).
Never calculates continuous 2D coordinates. Strictly validated with Pydantic.
"""

import json
import logging
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings

logger = logging.getLogger("saf_studio.groq_client")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqLayoutRecommendation(BaseModel):
    """Pydantic schema enforcing structured output from Groq LLM."""

    recommended_style: Literal["grid", "salon", "centre", "row"] = Field(
        description="Curated layout archetype best matching room proportions and photo collection"
    )
    focal_photo_id: str | None = Field(
        default=None,
        description="Item ID of the photo selected as the primary focal point / anchor",
    )
    photo_order: list[str] = Field(
        default_factory=list,
        description="Recommended display sequence of photo item IDs for visual balance",
    )
    spacing_inches: float = Field(
        default=3.0,
        ge=1.0,
        le=8.0,
        description="Suggested gap between frames in inches",
    )
    rationale: str = Field(
        default="",
        description="Brief designer explanation of why this composition was selected",
    )

    model_config = ConfigDict(extra="ignore")


class GroqClient:
    """Resilient async client for Groq text chat completions."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client

    async def get_curator_recommendation(
        self,
        wall: dict[str, Any],
        photos: list[dict[str, Any]],
        current_style: str | None = None,
        is_redesign: bool = False,
    ) -> tuple[GroqLayoutRecommendation | None, int]:
        """Request compositional curation recommendations from Groq.

        Returns (recommendation, tokens_used). If Groq is disabled, times out,
        or errors, returns (None, 0) to trigger seamless geometric fallback.
        """
        if not self.settings.GROQ_ENABLED or not self.settings.GROQ_API_KEY:
            logger.debug("Groq inference skipped: GROQ_ENABLED is False or API key unset")
            return None, 0

        # Build concise JSON payload
        system_instruction = (
            "You are an expert gallery wall art curator and interior designer. "
            "Analyze the wall dimensions and photo attributes to recommend the best layout style "
            "(grid, salon, centre, or row), focal photo, and ordering for visual harmony. "
            "Return valid JSON matching this schema: "
            '{"recommended_style": "grid"|"salon"|"centre"|"row", "focal_photo_id": "string", '
            '"photo_order": ["id1", "id2"], "spacing_inches": 3.0, "rationale": "string"}. '
            "Do NOT calculate x/y coordinates. Only output the JSON object."
        )

        user_content = json.dumps(
            {
                "wall": {
                    "width_inches": wall.get("width_inches"),
                    "height_inches": wall.get("height_inches"),
                    "has_furniture": wall.get("has_sofa", False),
                },
                "photos": [
                    {
                        "item_id": p.get("item_id"),
                        "aspect_ratio": p.get("aspect_ratio"),
                        "orientation": p.get("orientation"),
                        "color_temp": p.get("color_temperature", "neutral"),
                        "visual_weight": p.get("visual_weight", 0.5),
                    }
                    for p in photos
                ],
                "current_style": current_style,
                "goal": "redesign_different" if is_redesign else "optimal_balance",
            },
            separators=(",", ":"),
        )

        request_body = {
            "model": self.settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7 if is_redesign else 0.2,
            "max_tokens": self.settings.GROQ_MAX_OUTPUT_TOKENS,
        }

        headers = {
            "Authorization": f"Bearer {self.settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        timeout = httpx.Timeout(self.settings.GROQ_TIMEOUT_SECONDS)

        try:
            if self._client:
                response = await self._client.post(
                    GROQ_API_URL, json=request_body, headers=headers, timeout=timeout
                )
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(GROQ_API_URL, json=request_body, headers=headers)

            if response.status_code == 429:
                logger.warning("Groq rate limit exceeded (429). Falling back to geometry engine.")
                return None, 0

            if response.status_code != 200:
                logger.warning(
                    "Groq API returned status %s: %s", response.status_code, response.text
                )
                return None, 0

            res_json = response.json()
            usage = res_json.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)

            choices = res_json.get("choices", [])
            if not choices:
                return None, total_tokens

            message_content = choices[0].get("message", {}).get("content", "{}")
            parsed_dict = json.loads(message_content)

            # Validate against strict Pydantic model
            recommendation = GroqLayoutRecommendation(**parsed_dict)

            # Verify that recommended IDs actually exist in request photos
            valid_ids = {p.get("item_id") for p in photos}
            if recommendation.focal_photo_id and recommendation.focal_photo_id not in valid_ids:
                recommendation.focal_photo_id = None

            # Filter photo order to only known IDs
            recommendation.photo_order = [
                pid for pid in recommendation.photo_order if pid in valid_ids
            ]

            return recommendation, total_tokens

        except httpx.TimeoutException:
            logger.warning(
                "Groq request timed out after %ss. Falling back to geometry.",
                self.settings.GROQ_TIMEOUT_SECONDS,
            )
            return None, 0
        except Exception as exc:
            logger.warning("Groq inference error: %s. Falling back to geometry.", exc)
            return None, 0

    async def check_health(self) -> dict[str, Any]:
        """Verify Groq AI Curator configuration and inference connectivity."""
        import time

        if not self.settings.GROQ_ENABLED:
            return {
                "status": "disabled",
                "enabled": False,
                "model": self.settings.GROQ_MODEL,
            }

        api_key = self.settings.GROQ_API_KEY.strip()
        if not api_key:
            return {
                "status": "misconfigured",
                "enabled": True,
                "model": self.settings.GROQ_MODEL,
                "issue": "GROQ_API_KEY is not set",
            }

        start = time.perf_counter()
        timeout = httpx.Timeout(3.0)
        try:
            if self._client:
                resp = await self._client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(
                        "https://api.groq.com/openai/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
            latency = round((time.perf_counter() - start) * 1000, 2)
            if resp.status_code == 200:
                return {
                    "status": "ready",
                    "enabled": True,
                    "model": self.settings.GROQ_MODEL,
                    "latency_ms": latency,
                }
            return {
                "status": "degraded",
                "enabled": True,
                "model": self.settings.GROQ_MODEL,
                "issue": f"Groq API returned HTTP {resp.status_code}",
                "latency_ms": latency,
            }
        except Exception as exc:
            return {
                "status": "unreachable",
                "enabled": True,
                "model": self.settings.GROQ_MODEL,
                "issue": str(exc),
            }
