"""Intelligent Wall Layout Generation & Regeneration Service.

Orchestrates local photo metadata extraction, Groq AI creative recommendations,
and authoritative Python deterministic geometry solving.
"""

import logging
from typing import Any

from app.integrations.groq_client import GroqClient, GroqLayoutRecommendation
from app.modules.geometry import (
    FrameGeometry,
    Scene,
    build_scene,
    compute_frame_geometry,
    new_seed,
    suggest_layouts,
    validate_placed_frames,
)
from app.repositories.ai_cache_repository import AICacheRepository
from app.repositories.photo_repository import PhotoRepository
from app.schemas.geometry import (
    BoundingBox,
    FrameItemInput,
    GenerateLayoutRequest,
    GenerateLayoutResponse,
    GeometryValidationWarningItem,
    PlacedItemOutput,
    RegenerateLayoutRequest,
    RegenerateLayoutResponse,
    ValidateLayoutRequest,
    ValidateLayoutResponse,
)
from app.services.ai_usage_service import AIUsageService
from app.services.photo_analysis_service import PhotoAnalysisService

logger = logging.getLogger("saf_studio.layout_service")


class LayoutService:
    """Core domain service for gallery wall generation, regeneration, and validation."""

    def __init__(
        self,
        photo_repo: PhotoRepository,
        photo_analysis_service: PhotoAnalysisService,
        groq_client: GroqClient,
        ai_usage_service: AIUsageService,
        ai_cache_repo: AICacheRepository,
    ) -> None:
        self.photo_repo = photo_repo
        self.photo_analysis_service = photo_analysis_service
        self.groq_client = groq_client
        self.ai_usage_service = ai_usage_service
        self.ai_cache_repo = ai_cache_repo

    async def _enrich_frames_with_photos(
        self,
        frames: list[FrameItemInput],
        current_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch photo metadata and cached visual analysis for each frame."""
        enriched: list[dict[str, Any]] = []

        for f in frames:
            item_data: dict[str, Any] = {
                "item_id": f.item_id,
                "photo_id": f.photo_id,
                "photo_width_inches": f.photo_width_inches,
                "photo_height_inches": f.photo_height_inches,
                "aspect_ratio": round(f.photo_width_inches / f.photo_height_inches, 4)
                if f.photo_height_inches > 0
                else 1.0,
                "orientation": f.orientation,
                "mat_inches": f.matting.top_inches if f.matting.enabled else 0.0,
                "profile_inches": f.frame_profile_width_inches,
                "color_temperature": "neutral",
                "visual_weight": 0.5,
            }

            # If user provided a valid photo_id from their library, load trusted analysis
            if f.photo_id:
                photo_doc = await self.photo_repo.get_by_id(f.photo_id)
                if photo_doc:
                    # Enforce tenancy if user is authenticated
                    if current_user_id and str(photo_doc.user_id) != str(current_user_id):
                        logger.warning(
                            "Unauthorized attempt to reference photo %s by user %s",
                            f.photo_id,
                            current_user_id,
                        )
                    else:
                        analysis = await self.photo_analysis_service.get_or_analyze_photo(
                            photo_doc, current_user_id
                        )
                        item_data["color_temperature"] = analysis.color_temperature
                        item_data["visual_weight"] = analysis.visual_weight
                        item_data["aspect_ratio"] = photo_doc.aspect_ratio

            enriched.append(item_data)

        return enriched

    @staticmethod
    def _to_frame_geometry(items: list[dict[str, Any]]) -> list[FrameGeometry]:
        return [
            compute_frame_geometry(
                item_id=it["item_id"],
                opening_w=it["photo_width_inches"],
                opening_h=it["photo_height_inches"],
                mat_in=it["mat_inches"],
                profile_in=it["profile_inches"],
            )
            for it in items
        ]

    @staticmethod
    def _scene_to_placed_items(
        scene: Scene, frame_map: dict[str, dict[str, Any]]
    ) -> list[PlacedItemOutput]:
        items: list[PlacedItemOutput] = []
        for pf in scene.frames:
            meta = frame_map.get(pf.item_id, {})
            items.append(
                PlacedItemOutput(
                    item_id=pf.item_id,
                    photo_id=meta.get("photo_id"),
                    outer_x_inches=round(pf.outer_rect.x, 2),
                    outer_y_inches=round(pf.outer_rect.y, 2),
                    outer_width_inches=round(pf.outer_rect.w, 2),
                    outer_height_inches=round(pf.outer_rect.h, 2),
                    photo_x_inches=round(pf.photo_rect.x, 2),
                    photo_y_inches=round(pf.photo_rect.y, 2),
                    photo_width_inches=round(pf.photo_rect.w, 2),
                    photo_height_inches=round(pf.photo_rect.h, 2),
                )
            )
        return items

    # ==========================================================================
    # 1. Generate Layout
    # ==========================================================================

    async def generate_layout(
        self,
        req: GenerateLayoutRequest,
        caller_id: str,
        current_user_id: str | None = None,
    ) -> GenerateLayoutResponse:
        """Generate an optimal, collision-free gallery wall layout."""
        enriched = await self._enrich_frames_with_photos(req.frames, current_user_id)
        frame_map = {it["item_id"]: it for it in enriched}
        seed = req.seed if req.seed is not None else new_seed()
        engine_used = req.engine_mode
        ai_rationale: str | None = None

        recommendation: GroqLayoutRecommendation | None = None

        # Tier 2: Groq Smart LLM Mode
        if req.engine_mode == "smart_llm":
            wall_spec = {
                "width_inches": req.wall.width_inches,
                "height_inches": req.wall.height_inches,
                "has_sofa": req.wall.has_sofa,
            }
            cache_key = self.ai_cache_repo.compute_cache_key(
                wall=wall_spec,
                photos=enriched,
                current_style=req.layout_style,
                is_redesign=False,
            )

            # Check cache first (0 tokens)
            cached_rec = self.ai_cache_repo.get(cache_key)
            if cached_rec:
                recommendation = cached_rec
                logger.info("Serving Groq recommendation from cache")
            elif self.ai_usage_service.can_make_request(caller_id):
                recommendation, tokens_used = await self.groq_client.get_curator_recommendation(
                    wall=wall_spec,
                    photos=enriched,
                    current_style=req.layout_style,
                    is_redesign=False,
                )
                if recommendation:
                    self.ai_usage_service.record_usage(caller_id, tokens_used)
                    self.ai_cache_repo.set(cache_key, recommendation)

            if recommendation:
                ai_rationale = recommendation.rationale
                chosen_style = recommendation.recommended_style
                spacing = recommendation.spacing_inches

                # Reorder frames if recommended
                if recommendation.photo_order:
                    order_map = {pid: idx for idx, pid in enumerate(recommendation.photo_order)}
                    enriched.sort(key=lambda x: order_map.get(x["item_id"], 999))
            else:
                # Seamless fallback to geometry engine
                engine_used = "fallback_geometric"
                chosen_style = req.layout_style
                spacing = req.spacing_inches
        else:
            chosen_style = req.layout_style
            spacing = req.spacing_inches

        # Tier 3: Deterministic Python Geometry Engine
        geoms = self._to_frame_geometry(enriched)

        if chosen_style is not None:
            # User or AI specified style
            scene = build_scene(
                wall_w=req.wall.width_inches,
                wall_h=req.wall.height_inches,
                frames=geoms,
                style=chosen_style,
                gap=spacing,
                variant=req.variant,
                seed=seed,
                margin_in=req.wall.margin_inches,
                has_sofa=req.wall.has_sofa,
                eye_level_in=req.wall.eye_level_height_inches,
            )
            final_style = chosen_style
            final_variant = req.variant
        else:
            # Algorithmic mode: score all styles & variants to find best fit
            suggestions = suggest_layouts(
                wall_w=req.wall.width_inches,
                wall_h=req.wall.height_inches,
                frames=geoms,
                gap=spacing,
                seed=seed,
                margin_in=req.wall.margin_inches,
                has_sofa=req.wall.has_sofa,
                eye_level_in=req.wall.eye_level_height_inches,
            )
            best = suggestions[0]
            scene = best.scene
            final_style = best.style
            final_variant = best.variant

        placed_items = self._scene_to_placed_items(scene, frame_map)

        return GenerateLayoutResponse(
            layout_type=final_style,
            variant=final_variant,
            seed=seed,
            bounding_box=BoundingBox(
                x=round(scene.arrangement.x, 2),
                y=round(scene.arrangement.y, 2),
                width=round(scene.arrangement.w, 2),
                height=round(scene.arrangement.h, 2),
            ),
            wall_coverage_percentage=round(scene.coverage * 100.0, 2),
            fits=scene.fits,
            engine_used=engine_used,
            ai_rationale=ai_rationale,
            warnings=[
                GeometryValidationWarningItem(code=w.code, message=w.message)
                for w in scene.warnings
            ],
            items=placed_items,
        )

    # ==========================================================================
    # 2. Regenerate Layout (0 AI Tokens)
    # ==========================================================================

    async def regenerate_layout(
        self,
        req: RegenerateLayoutRequest,
        current_user_id: str | None = None,
    ) -> RegenerateLayoutResponse:
        """Regenerate layout exploring alternative valid arrangements with next seed.

        Zero AI calls guaranteed. Pure Python geometry math.
        """
        enriched = await self._enrich_frames_with_photos(req.frames, current_user_id)
        frame_map = {it["item_id"]: it for it in enriched}

        # Mutate seed deterministically to next alternative
        next_seed = (req.current_seed * 1664525 + 1013904223) & 0xFFFFFFFF
        next_variant = (req.current_variant + 1) % 3

        geoms = self._to_frame_geometry(enriched)
        scene = build_scene(
            wall_w=req.wall.width_inches,
            wall_h=req.wall.height_inches,
            frames=geoms,
            style=req.layout_style,
            gap=req.spacing_inches,
            variant=next_variant,
            seed=next_seed,
            margin_in=req.wall.margin_inches,
            has_sofa=req.wall.has_sofa,
            eye_level_in=req.wall.eye_level_height_inches,
        )

        placed_items = self._scene_to_placed_items(scene, frame_map)

        return RegenerateLayoutResponse(
            layout_type=req.layout_style,
            variant=next_variant,
            seed=next_seed,
            bounding_box=BoundingBox(
                x=round(scene.arrangement.x, 2),
                y=round(scene.arrangement.y, 2),
                width=round(scene.arrangement.w, 2),
                height=round(scene.arrangement.h, 2),
            ),
            wall_coverage_percentage=round(scene.coverage * 100.0, 2),
            fits=scene.fits,
            engine_used="geometric",
            items=placed_items,
        )

    # ==========================================================================
    # 3. Validate Layout (EP-GEO-01)
    # ==========================================================================

    def validate_layout(self, req: ValidateLayoutRequest) -> ValidateLayoutResponse:
        """Validate layout bounds, collisions, and clearances."""
        frames_data = [
            {
                "item_id": f.item_id,
                "outer_x_inches": f.outer_x_inches,
                "outer_y_inches": f.outer_y_inches,
                "outer_width_inches": f.outer_width_inches,
                "outer_height_inches": f.outer_height_inches,
            }
            for f in req.frames
        ]

        res = validate_placed_frames(
            wall_w=req.wall.width_inches,
            wall_h=req.wall.height_inches,
            frames=frames_data,
            margin_in=req.wall.margin_inches,
            has_sofa=req.wall.has_sofa,
        )

        return ValidateLayoutResponse(
            is_valid=res.is_valid,
            bounding_box=BoundingBox(
                x=round(res.bounding_box.x, 2),
                y=round(res.bounding_box.y, 2),
                width=round(res.bounding_box.w, 2),
                height=round(res.bounding_box.h, 2),
            ),
            wall_coverage_percentage=res.wall_coverage_percentage,
            errors=[
                {"code": err.code, "message": err.message, "item_ids": err.item_ids}
                for err in res.errors
            ],
            warnings=[{"code": w.code, "message": w.message} for w in res.warnings],
            calculated_items=res.calculated_items,
        )
