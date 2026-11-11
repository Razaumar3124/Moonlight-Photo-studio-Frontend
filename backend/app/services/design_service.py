import logging
import math
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
    ValidationException,
)
from app.models.design import DesignInDB, DesignWallInDB
from app.models.design_version import (
    BoundingBoxInDB,
    DesignItemInDB,
    DesignVersionInDB,
    MattingInDB,
)
from app.modules.geometry.validation import validate_placed_frames
from app.repositories.design_repository import DesignRepository
from app.repositories.photo_repository import PhotoRepository
from app.schemas.design import (
    BoundingBoxSchema,
    CreateDesignRequest,
    DesignDetailOut,
    DesignItemOutput,
    DesignListItemOut,
    DesignListResponse,
    DesignOut,
    DesignVersionOutput,
    DesignVersionSummaryResponse,
    DesignWallSchema,
    MattingInputSchema,
    SaveDesignVersionRequest,
    UpdateDesignRequest,
)

logger = logging.getLogger("saf_studio.design_service")


class DesignService:
    """Business logic service for gallery wall designs and immutable version snapshots."""

    def __init__(
        self,
        design_repo: DesignRepository,
        photo_repo: PhotoRepository,
    ) -> None:
        self.design_repo = design_repo
        self.photo_repo = photo_repo

    async def create_design(
        self,
        user_id: str,
        req: CreateDesignRequest,
    ) -> DesignOut:
        """Create a new design draft owned by the authenticated user (EP-DSGN-01)."""
        wall_in_db = DesignWallInDB(
            width_inches=req.wall.width_inches,
            height_inches=req.wall.height_inches,
            color_hex=req.wall.color_hex,
            texture=req.wall.texture,
            display_unit=req.wall.display_unit,
            has_sofa=req.wall.has_sofa,
        )

        now = datetime.now(UTC)
        design = DesignInDB(
            user_id=user_id,
            title=req.title.strip(),
            description=req.description.strip() if req.description else None,
            wall=wall_in_db,
            status="draft",
            current_version_id=None,
            current_version_number=None,
            version_counter=0,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )

        saved = await self.design_repo.create_design(design)
        logger.info("Created new design draft '%s' for user '%s'", saved.id, user_id)

        return DesignOut(
            id=saved.id,
            user_id=saved.user_id,
            title=saved.title,
            description=saved.description,
            wall=DesignWallSchema(
                width_inches=saved.wall.width_inches,
                height_inches=saved.wall.height_inches,
                color_hex=saved.wall.color_hex,
                texture=saved.wall.texture,
                display_unit=saved.wall.display_unit,  # type: ignore[arg-type]
                has_sofa=saved.wall.has_sofa,
            ),
            current_version_id=saved.current_version_id,
            current_version_number=saved.current_version_number,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )

    async def get_design(
        self,
        design_id: str,
        user_id: str,
    ) -> DesignDetailOut:
        """Retrieve a saved design with its current layout version (EP-DSGN-03)."""
        if not ObjectId.is_valid(design_id):
            raise ResourceNotFoundException(f"Design '{design_id}' not found.", field="id")

        design = await self.design_repo.get_design_by_id(design_id)
        if not design:
            raise ResourceNotFoundException(f"Design '{design_id}' not found.", field="id")

        # Ownership authorization check (BOLA / IDOR protection)
        if design.user_id != user_id:
            logger.warning(
                "IDOR attempt: User '%s' attempted to access design '%s' owned by '%s'",
                user_id,
                design_id,
                design.user_id,
            )
            raise ForbiddenException(
                "You do not have permission to access this design.", field="id"
            )

        version_out: DesignVersionOutput | None = None
        if design.current_version_id:
            version_in_db = await self.design_repo.get_version_by_id(design.current_version_id)
            if version_in_db:
                # Resolve photo availability (Missing-photo strategy)
                item_outputs: list[DesignItemOutput] = []
                for item in version_in_db.items:
                    photo_missing = False
                    if item.photo_id:
                        photo = await self.photo_repo.get_by_id(item.photo_id)
                        if photo is None or photo.is_deleted:
                            photo_missing = True

                    item_outputs.append(
                        DesignItemOutput(
                            item_id=item.item_id,
                            frame_id=item.frame_id,
                            photo_id=item.photo_id,
                            photo_missing=photo_missing,
                            sample_id=item.sample_id,
                            position_x_inches=item.position_x_inches,
                            position_y_inches=item.position_y_inches,
                            photo_width_inches=item.photo_width_inches,
                            photo_height_inches=item.photo_height_inches,
                            total_width_inches=item.total_width_inches,
                            total_height_inches=item.total_height_inches,
                            orientation=item.orientation,
                            finish_id=item.finish_id,
                            size_id=item.size_id,
                            matting=MattingInputSchema(
                                enabled=item.matting.enabled,
                                top_inches=item.matting.top_inches,
                                bottom_inches=item.matting.bottom_inches,
                                left_inches=item.matting.left_inches,
                                right_inches=item.matting.right_inches,
                                color_hex=item.matting.color_hex,
                            ),
                            glass_type=item.glass_type,
                        )
                    )

                version_out = DesignVersionOutput(
                    id=version_in_db.id,
                    design_id=version_in_db.design_id,
                    version_number=version_in_db.version_number,
                    layout_type=version_in_db.layout_type,
                    template_id=version_in_db.template_id,
                    items_count=len(version_in_db.items),
                    bounding_box=BoundingBoxSchema(
                        x=version_in_db.bounding_box.x,
                        y=version_in_db.bounding_box.y,
                        width=version_in_db.bounding_box.width,
                        height=version_in_db.bounding_box.height,
                    ),
                    items=item_outputs,
                    layout_metadata=version_in_db.layout_metadata,
                    preview=version_in_db.preview,
                    created_at=version_in_db.created_at,
                )

        return DesignDetailOut(
            id=design.id,
            user_id=design.user_id,
            title=design.title,
            description=design.description,
            status=design.status,
            wall=DesignWallSchema(
                width_inches=design.wall.width_inches,
                height_inches=design.wall.height_inches,
                color_hex=design.wall.color_hex,
                texture=design.wall.texture,
                display_unit=design.wall.display_unit,  # type: ignore[arg-type]
                has_sofa=design.wall.has_sofa,
            ),
            current_version_id=design.current_version_id,
            current_version=version_out,
            created_at=design.created_at,
            updated_at=design.updated_at,
        )

    async def list_designs(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
        sort: str = "updated_at:desc",
    ) -> DesignListResponse:
        """List active designs owned by authenticated user (EP-DSGN-04)."""
        page = max(1, page)
        page_size = max(1, min(100, page_size))

        designs, total = await self.design_repo.list_designs_by_user(
            user_id=user_id,
            page=page,
            page_size=page_size,
            status=status,
            search=search,
            sort=sort,
        )

        items_out: list[DesignListItemOut] = []
        for d in designs:
            items_count = 0
            if d.current_version_id:
                ver = await self.design_repo.get_version_by_id(d.current_version_id)
                if ver:
                    items_count = len(ver.items)

            items_out.append(
                DesignListItemOut(
                    id=d.id,
                    user_id=d.user_id,
                    title=d.title,
                    description=d.description,
                    status=d.status,
                    wall=DesignWallSchema(
                        width_inches=d.wall.width_inches,
                        height_inches=d.wall.height_inches,
                        color_hex=d.wall.color_hex,
                        texture=d.wall.texture,
                        display_unit=d.wall.display_unit,  # type: ignore[arg-type]
                        has_sofa=d.wall.has_sofa,
                    ),
                    current_version_id=d.current_version_id,
                    current_version_number=d.current_version_number,
                    items_count=items_count,
                    created_at=d.created_at,
                    updated_at=d.updated_at,
                )
            )

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return DesignListResponse(
            items=items_out,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def update_design(
        self,
        design_id: str,
        user_id: str,
        req: UpdateDesignRequest,
    ) -> DesignOut:
        """Update top-level design metadata (EP-DSGN-05)."""
        if not ObjectId.is_valid(design_id):
            raise ResourceNotFoundException(f"Design '{design_id}' not found.", field="id")

        design = await self.design_repo.get_design_by_id(design_id)
        if not design:
            raise ResourceNotFoundException(f"Design '{design_id}' not found.", field="id")

        if design.user_id != user_id:
            raise ForbiddenException(
                "You do not have permission to modify this design.", field="id"
            )

        updates: dict[str, Any] = {}
        if req.title is not None:
            updates["title"] = req.title.strip()
        if req.description is not None:
            updates["description"] = req.description.strip()
        if req.status is not None:
            updates["status"] = req.status
        if req.wall is not None:
            updates["wall"] = DesignWallInDB(
                width_inches=req.wall.width_inches,
                height_inches=req.wall.height_inches,
                color_hex=req.wall.color_hex,
                texture=req.wall.texture,
                display_unit=req.wall.display_unit,
                has_sofa=req.wall.has_sofa,
            ).model_dump()

        updated = await self.design_repo.update_design(design_id, updates)
        if not updated:
            raise ResourceNotFoundException(f"Design '{design_id}' not found.", field="id")

        return DesignOut(
            id=updated.id,
            user_id=updated.user_id,
            title=updated.title,
            description=updated.description,
            wall=DesignWallSchema(
                width_inches=updated.wall.width_inches,
                height_inches=updated.wall.height_inches,
                color_hex=updated.wall.color_hex,
                texture=updated.wall.texture,
                display_unit=updated.wall.display_unit,  # type: ignore[arg-type]
                has_sofa=updated.wall.has_sofa,
            ),
            current_version_id=updated.current_version_id,
            current_version_number=updated.current_version_number,
            status=updated.status,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )

    async def delete_design(
        self,
        design_id: str,
        user_id: str,
    ) -> None:
        """Soft-delete an owned design (EP-DSGN-06). Preserves photos."""
        if not ObjectId.is_valid(design_id):
            raise ResourceNotFoundException(f"Design '{design_id}' not found.", field="id")

        design = await self.design_repo.get_design_by_id(design_id)
        if not design:
            raise ResourceNotFoundException(f"Design '{design_id}' not found.", field="id")

        if design.user_id != user_id:
            raise ForbiddenException(
                "You do not have permission to delete this design.", field="id"
            )

        await self.design_repo.delete_design(design_id)
        logger.info("Design '%s' soft-deleted by user '%s'", design_id, user_id)

    async def create_version(
        self,
        design_id: str,
        user_id: str,
        req: SaveDesignVersionRequest,
    ) -> DesignVersionSummaryResponse:
        """Create an immutable snapshot version of a design layout (EP-DSGN-02)."""
        if not ObjectId.is_valid(design_id):
            raise ResourceNotFoundException(f"Design '{design_id}' not found.", field="id")

        design = await self.design_repo.get_design_by_id(design_id)
        if not design:
            raise ResourceNotFoundException(f"Design '{design_id}' not found.", field="id")

        if design.user_id != user_id:
            raise ForbiddenException(
                "You do not have permission to create a version for this design.", field="id"
            )

        # 1. Validate Photo References (Cross-user photo protection)
        for item in req.items:
            if item.photo_id:
                if not ObjectId.is_valid(item.photo_id):
                    raise ValidationException(
                        f"Invalid photo ObjectId format: '{item.photo_id}'.",
                        details=[
                            {
                                "field": f"items.{item.item_id}.photo_id",
                                "issue": "Malformed ObjectId",
                            }
                        ],
                    )
                photo = await self.photo_repo.get_by_id(item.photo_id)
                if photo is None:
                    raise ValidationException(
                        f"Photo '{item.photo_id}' referenced by frame '{item.item_id}' not found.",
                        details=[
                            {
                                "field": f"items.{item.item_id}.photo_id",
                                "issue": "Photo does not exist",
                            }
                        ],
                    )
                if str(photo.user_id) != user_id:
                    logger.warning(
                        "BOLA/IDOR photo violation: User '%s' referenced photo '%s' owned by '%s'",
                        user_id,
                        item.photo_id,
                        photo.user_id,
                    )
                    raise ForbiddenException(
                        f"Unauthorized photo reference: '{item.photo_id}' is not owned by you.",
                        field=f"items.{item.item_id}.photo_id",
                    )

        # 2. Compute frame dimensions and matting
        resolved_items: list[DesignItemInDB] = []
        geo_frames: list[dict[str, Any]] = []

        for item in req.items:
            matting_w = (
                (item.matting.left_inches + item.matting.right_inches)
                if item.matting.enabled
                else 0.0
            )
            matting_h = (
                (item.matting.top_inches + item.matting.bottom_inches)
                if item.matting.enabled
                else 0.0
            )
            total_w = item.total_width_inches or round(item.photo_width_inches + matting_w, 2)
            total_h = item.total_height_inches or round(item.photo_height_inches + matting_h, 2)

            resolved_items.append(
                DesignItemInDB(
                    item_id=item.item_id,
                    frame_id=item.frame_id,
                    photo_id=item.photo_id,
                    sample_id=item.sample_id,
                    position_x_inches=item.position_x_inches,
                    position_y_inches=item.position_y_inches,
                    photo_width_inches=item.photo_width_inches,
                    photo_height_inches=item.photo_height_inches,
                    total_width_inches=total_w,
                    total_height_inches=total_h,
                    orientation=item.orientation,
                    finish_id=item.finish_id,
                    size_id=item.size_id,
                    matting=MattingInDB(
                        enabled=item.matting.enabled,
                        top_inches=item.matting.top_inches,
                        bottom_inches=item.matting.bottom_inches,
                        left_inches=item.matting.left_inches,
                        right_inches=item.matting.right_inches,
                        color_hex=item.matting.color_hex,
                    ),
                    glass_type=item.glass_type,
                )
            )

            geo_frames.append(
                {
                    "item_id": item.item_id,
                    "outer_x_inches": item.position_x_inches,
                    "outer_y_inches": item.position_y_inches,
                    "outer_width_inches": total_w,
                    "outer_height_inches": total_h,
                }
            )

        # 3. Geometry Validation using Phase 5 validator (no Groq AI calls)
        geo_result = validate_placed_frames(
            wall_w=design.wall.width_inches,
            wall_h=design.wall.height_inches,
            frames=geo_frames,
            margin_in=6.0,
            has_sofa=design.wall.has_sofa,
        )

        if geo_result.errors:
            error_details = [
                {
                    "field": f"items.{err.item_ids[0]}" if err.item_ids else "items",
                    "issue": err.message,
                }
                for err in geo_result.errors
            ]
            raise ValidationException(
                message="Layout geometry violates wall boundaries or contains invalid dimensions.",
                details=error_details,
            )

        # 4. Compute 2D Axis-Aligned Bounding Box
        min_x = min(item.position_x_inches for item in resolved_items)
        min_y = min(item.position_y_inches for item in resolved_items)
        max_x = max(item.position_x_inches + item.total_width_inches for item in resolved_items)
        max_y = max(item.position_y_inches + item.total_height_inches for item in resolved_items)

        bounding_box = BoundingBoxInDB(
            x=round(min_x, 2),
            y=round(min_y, 2),
            width=round(max_x - min_x, 2),
            height=round(max_y - min_y, 2),
        )

        # 5. Check for redundant identical snapshot
        if design.current_version_id:
            latest = await self.design_repo.get_version_by_id(design.current_version_id)
            if latest and self._is_identical_version(
                latest, req.layout_type, req.template_id, resolved_items
            ):
                logger.info(
                    "Duplicate version request ignored for '%s'; returning version %s",
                    design_id,
                    latest.version_number,
                )
                return DesignVersionSummaryResponse(
                    version_id=latest.id,
                    design_id=latest.design_id,
                    version_number=latest.version_number,
                    layout_type=latest.layout_type,
                    items_count=len(latest.items),
                    bounding_box=BoundingBoxSchema(
                        x=latest.bounding_box.x,
                        y=latest.bounding_box.y,
                        width=latest.bounding_box.width,
                        height=latest.bounding_box.height,
                    ),
                    created_at=latest.created_at,
                )

        # 6. Atomic version number acquisition
        version_number = await self.design_repo.get_next_version_number(design_id)

        # 7. Create immutable version record
        now = datetime.now(UTC)
        version = DesignVersionInDB(
            design_id=design_id,
            version_number=version_number,
            layout_type=req.layout_type,
            template_id=req.template_id,
            items=resolved_items,
            bounding_box=bounding_box,
            layout_metadata=req.layout_metadata,
            preview=req.preview,
            created_at=now,
        )

        saved_version = await self.design_repo.create_version(version)

        # 8. Update parent design pointers
        await self.design_repo.update_design(
            design_id,
            {
                "current_version_id": saved_version.id,
                "current_version_number": saved_version.version_number,
                "status": "saved",
            },
        )

        logger.info(
            "Created version %s for design '%s' (version_id: %s)",
            version_number,
            design_id,
            saved_version.id,
        )

        return DesignVersionSummaryResponse(
            version_id=saved_version.id,
            design_id=saved_version.design_id,
            version_number=saved_version.version_number,
            layout_type=saved_version.layout_type,
            items_count=len(saved_version.items),
            bounding_box=BoundingBoxSchema(
                x=saved_version.bounding_box.x,
                y=saved_version.bounding_box.y,
                width=saved_version.bounding_box.width,
                height=saved_version.bounding_box.height,
            ),
            created_at=saved_version.created_at,
        )

    def _is_identical_version(
        self,
        latest: DesignVersionInDB,
        layout_type: str,
        template_id: str | None,
        new_items: list[DesignItemInDB],
    ) -> bool:
        """Determine whether new version payload exactly mirrors current version snapshot."""
        if latest.layout_type != layout_type or latest.template_id != template_id:
            return False
        if len(latest.items) != len(new_items):
            return False

        for old_it, new_it in zip(latest.items, new_items, strict=False):
            if (
                old_it.item_id != new_it.item_id
                or old_it.frame_id != new_it.frame_id
                or old_it.photo_id != new_it.photo_id
                or old_it.sample_id != new_it.sample_id
                or abs(old_it.position_x_inches - new_it.position_x_inches) > 0.01
                or abs(old_it.position_y_inches - new_it.position_y_inches) > 0.01
                or abs(old_it.photo_width_inches - new_it.photo_width_inches) > 0.01
                or abs(old_it.photo_height_inches - new_it.photo_height_inches) > 0.01
                or old_it.orientation != new_it.orientation
                or old_it.finish_id != new_it.finish_id
            ):
                return False

        return True
