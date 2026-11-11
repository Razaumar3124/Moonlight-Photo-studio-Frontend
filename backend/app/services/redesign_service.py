"""Wall Layout Redesign Service.

Delivers a meaningfully different composition or arrangement style by cycling archetypes
or requesting creative directions from the Groq curator, resolved by the Python geometry engine.
"""

import logging
from typing import Any

from app.integrations.groq_client import GroqClient
from app.modules.geometry import (
    LAYOUT_STYLES,
    LayoutStyle,
    build_scene,
    compute_frame_geometry,
    new_seed,
)
from app.repositories.ai_cache_repository import AICacheRepository
from app.repositories.photo_repository import PhotoRepository
from app.schemas.geometry import (
    BoundingBox,
    PlacedItemOutput,
    RedesignLayoutRequest,
    RedesignLayoutResponse,
)
from app.services.ai_usage_service import AIUsageService
from app.services.photo_analysis_service import PhotoAnalysisService

logger = logging.getLogger("saf_studio.redesign_service")


class RedesignService:
    """Service handling 'Redesign Layout' operations."""

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

    @staticmethod
    def _next_archetype(current: LayoutStyle) -> LayoutStyle:
        """Advance to next structural archetype in sequence."""
        try:
            idx = LAYOUT_STYLES.index(current)
            return LAYOUT_STYLES[(idx + 1) % len(LAYOUT_STYLES)]
        except ValueError:
            return "salon"

    async def redesign_layout(
        self,
        req: RedesignLayoutRequest,
        caller_id: str,
        current_user_id: str | None = None,
    ) -> RedesignLayoutResponse:
        """Produce a structurally different layout composition."""
        # 1. Enrich frames with photo data
        enriched: list[dict[str, Any]] = []
        for f in req.frames:
            it: dict[str, Any] = {
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
            if f.photo_id:
                photo_doc = await self.photo_repo.get_by_id(f.photo_id)
                if photo_doc and (
                    not current_user_id or str(photo_doc.user_id) == str(current_user_id)
                ):
                    analysis = await self.photo_analysis_service.get_or_analyze_photo(
                        photo_doc, current_user_id
                    )
                    it["color_temperature"] = analysis.color_temperature
                    it["visual_weight"] = analysis.visual_weight
            enriched.append(it)

        frame_map = {it["item_id"]: it for it in enriched}
        engine_used = req.engine_mode
        ai_rationale: str | None = None
        seed = new_seed()

        target_style: LayoutStyle | None = None

        # 2. Check Groq in smart mode
        if req.engine_mode == "smart_llm":
            wall_spec = {
                "width_inches": req.wall.width_inches,
                "height_inches": req.wall.height_inches,
                "has_sofa": req.wall.has_sofa,
            }
            cache_key = self.ai_cache_repo.compute_cache_key(
                wall=wall_spec,
                photos=enriched,
                current_style=req.current_layout_style,
                is_redesign=True,
            )
            cached_rec = self.ai_cache_repo.get(cache_key)

            if cached_rec and cached_rec.recommended_style != req.current_layout_style:
                rec = cached_rec
            elif self.ai_usage_service.can_make_request(caller_id):
                rec, tokens_used = await self.groq_client.get_curator_recommendation(
                    wall=wall_spec,
                    photos=enriched,
                    current_style=req.current_layout_style,
                    is_redesign=True,
                )
                if rec:
                    self.ai_usage_service.record_usage(caller_id, tokens_used)
                    self.ai_cache_repo.set(cache_key, rec)
            else:
                rec = None

            if rec and rec.recommended_style != req.current_layout_style:
                target_style = rec.recommended_style
                ai_rationale = rec.rationale
            else:
                engine_used = "fallback_geometric"
                target_style = self._next_archetype(req.current_layout_style)
        else:
            target_style = self._next_archetype(req.current_layout_style)

        # 3. Solve geometry with target archetype
        geoms = [
            compute_frame_geometry(
                item_id=it["item_id"],
                opening_w=it["photo_width_inches"],
                opening_h=it["photo_height_inches"],
                mat_in=it["mat_inches"],
                profile_in=it["profile_inches"],
            )
            for it in enriched
        ]

        scene = build_scene(
            wall_w=req.wall.width_inches,
            wall_h=req.wall.height_inches,
            frames=geoms,
            style=target_style,
            gap=req.spacing_inches,
            variant=0,
            seed=seed,
            margin_in=req.wall.margin_inches,
            has_sofa=req.wall.has_sofa,
            eye_level_in=req.wall.eye_level_height_inches,
        )

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

        return RedesignLayoutResponse(
            layout_type=target_style,
            variant=0,
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
            items=items,
        )
