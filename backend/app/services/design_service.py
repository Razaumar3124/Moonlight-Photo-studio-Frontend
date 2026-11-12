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
from app.modules import catalog
from app.modules.catalog import RULES
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
    DesignWallOut,
    DesignWallSchema,
    MattingOut,
    SaveDesignVersionRequest,
    UpdateDesignRequest,
)

logger = logging.getLogger("moonlight_studio.design_service")

# Tolerance for a client-supplied outer size against the server's computation.
OUTER_SIZE_TOLERANCE_IN = 0.05


def _wall_out(wall: DesignWallInDB) -> DesignWallOut:
    return DesignWallOut.model_validate(wall)


def _wall_in_db(wall: DesignWallSchema) -> DesignWallInDB:
    return DesignWallInDB(**wall.model_dump())


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
        wall_in_db = _wall_in_db(req.wall)

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
            wall=_wall_out(saved.wall),
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
                            matting=MattingOut.model_validate(item.matting),
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
            wall=_wall_out(design.wall),
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
                    wall=_wall_out(d.wall),
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
            updates["wall"] = _wall_in_db(req.wall).model_dump()

        updated = await self.design_repo.update_design(design_id, updates)
        if not updated:
            raise ResourceNotFoundException(f"Design '{design_id}' not found.", field="id")

        return DesignOut(
            id=updated.id,
            user_id=updated.user_id,
            title=updated.title,
            description=updated.description,
            wall=_wall_out(updated.wall),
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
                        "Invalid photo ID format.",
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

        # 2. Resolve outer sizes from the catalog and store catalog references
        resolved_items: list[DesignItemInDB] = []
        geo_frames: list[dict[str, Any]] = []

        for item in req.items:
            mat = item.matting
            mats = (
                (mat.left_inches, mat.right_inches, mat.top_inches, mat.bottom_inches)
                if mat.enabled
                else (0.0, 0.0, 0.0, 0.0)
            )
            if item.finish_id:
                # Authoritative: opening + mats + moulding face on both sides (frontend geometry).
                total_w, total_h = catalog.outer_size(
                    item.photo_width_inches,
                    item.photo_height_inches,
                    catalog.profile_inches(item.finish_id),
                    *mats,
                )
                for supplied, computed, axis in (
                    (item.total_width_inches, total_w, "width"),
                    (item.total_height_inches, total_h, "height"),
                ):
                    if supplied is not None and abs(supplied - computed) > OUTER_SIZE_TOLERANCE_IN:
                        raise ValidationException(
                            "Frame outer size doesn't match its size, mount and finish.",
                            details=[
                                {
                                    "field": f"items.{item.item_id}.total_{axis}_inches",
                                    "issue": f"Expected {computed:g} for this frame",
                                }
                            ],
                        )
            else:
                # No catalog finish (older clients): outer size as supplied, else opening + mats.
                total_w = item.total_width_inches or round(
                    item.photo_width_inches + mats[0] + mats[1], 4
                )
                total_h = item.total_height_inches or round(
                    item.photo_height_inches + mats[2] + mats[3], 4
                )

            resolved_items.append(
                DesignItemInDB(
                    item_id=item.item_id,
                    frame_id=item.frame_id or "custom",
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
                    matting=MattingInDB(**mat.model_dump()),
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

        layout_metadata = (
            req.layout_metadata.model_dump(exclude_none=True) if req.layout_metadata else None
        )
        preview = req.preview.model_dump(exclude_none=True) if req.preview else None

        # 3. Same fit rules as the planner: wall margin, minimum bottom or sofa clearance, no
        # overlaps. The version's sofa toggle wins over the design-level default.
        has_sofa = (
            req.preview.sofa
            if req.preview is not None and req.preview.sofa is not None
            else design.wall.has_sofa
        )
        geo_result = validate_placed_frames(
            wall_w=design.wall.width_inches,
            wall_h=design.wall.height_inches,
            frames=geo_frames,
            margin_in=RULES.wall_margin_inches,
            has_sofa=has_sofa,
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
            candidate = DesignVersionInDB(
                design_id=design_id,
                version_number=0,
                layout_type=req.layout_type,
                template_id=req.template_id,
                items=resolved_items,
                bounding_box=bounding_box,
                layout_metadata=layout_metadata,
                preview=preview,
            )
            if latest and self._is_identical_version(latest, candidate):
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
            layout_metadata=layout_metadata,
            preview=preview,
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

    @staticmethod
    def _is_identical_version(
        latest: DesignVersionInDB,
        candidate: DesignVersionInDB,
    ) -> bool:
        """True when `candidate` stores exactly what the current version already stores."""

        def comparable(version: DesignVersionInDB) -> dict[str, Any]:
            return version.model_dump(
                include={"layout_type", "template_id", "items", "layout_metadata", "preview"}
            )

        return comparable(latest) == comparable(candidate)
