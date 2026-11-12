from app.core.exceptions import ValidationException
from app.models.template import TemplateSlotInDB
from app.modules import catalog
from app.repositories.template_repository import TemplateRepository
from app.schemas.template import (
    LayoutTemplateOut,
    TemplatesListResponse,
    TemplateSlotOut,
)


def _slot_out(slot: TemplateSlotInDB) -> TemplateSlotOut:
    match = catalog.size_for_dimensions(
        slot.default_photo_width_inches, slot.default_photo_height_inches
    )
    return TemplateSlotOut(
        slot_id=slot.slot_id,
        relative_x_ratio=slot.relative_x_ratio,
        relative_y_ratio=slot.relative_y_ratio,
        default_photo_width_inches=slot.default_photo_width_inches,
        default_photo_height_inches=slot.default_photo_height_inches,
        aspect_ratio=slot.aspect_ratio,
        size_id=match[0].id if match else None,
        orientation=match[1]
        if match
        else (
            "landscape"
            if slot.default_photo_width_inches > slot.default_photo_height_inches
            else "portrait"
        ),
    )


class TemplateService:
    """Domain business logic for layout templates catalog."""

    def __init__(self, template_repo: TemplateRepository) -> None:
        self.template_repo = template_repo

    async def get_templates(
        self,
        category: str | None = None,
        min_frames: int | None = None,
        max_frames: int | None = None,
    ) -> TemplatesListResponse:
        """Retrieve list of gallery wall templates matching filter criteria."""
        if category:
            try:
                category = catalog.check_layout_style(category)
            except ValueError as exc:
                valid_str = ", ".join(catalog.LAYOUT_STYLE_IDS)
                raise ValidationException(
                    message=f"Invalid template category. Must be one of: {valid_str}.",
                    details=[{"field": "category", "issue": f"Supported categories: {valid_str}"}],
                ) from exc

        if min_frames is not None and min_frames < 1:
            raise ValidationException(
                message="min_frames must be at least 1.",
                details=[{"field": "min_frames", "issue": "Must be >= 1"}],
            )

        if max_frames is not None and max_frames < 1:
            raise ValidationException(
                message="max_frames must be at least 1.",
                details=[{"field": "max_frames", "issue": "Must be >= 1"}],
            )

        if min_frames is not None and max_frames is not None and min_frames > max_frames:
            raise ValidationException(
                message="min_frames cannot be greater than max_frames.",
                details=[
                    {
                        "field": "min_frames",
                        "issue": f"min_frames ({min_frames}) exceeds max_frames ({max_frames})",
                    }
                ],
            )

        templates = await self.template_repo.list_templates(
            category=category,
            min_frames=min_frames,
            max_frames=max_frames,
            active_only=True,
        )

        items = [
            LayoutTemplateOut(
                id=t.id,
                slug=t.slug,
                name=t.name,
                description=t.description,
                category=catalog.normalize_layout(t.category),
                gap_inches=t.gap_inches,
                min_wall_width_inches=t.min_wall_width_inches,
                min_wall_height_inches=t.min_wall_height_inches,
                recommended_wall_width_inches=t.recommended_wall_width_inches,
                recommended_wall_height_inches=t.recommended_wall_height_inches,
                slots_count=t.slots_count,
                slots=[_slot_out(slot) for slot in t.slots],
                thumbnail_url=t.thumbnail_url,
            )
            for t in templates
        ]
        return TemplatesListResponse(items=items, total=len(items))
