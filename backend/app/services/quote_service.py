"""Core Quote Service orchestrating design capture, validation, R2 storage, and WhatsApp linking."""

import hashlib
import io
import logging
from datetime import UTC, datetime, timedelta

from PIL import Image

from app.core.config import get_settings
from app.core.exceptions import (
    ForbiddenException,
    IdempotencyConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.security import generate_secure_token, hash_token
from app.models.quote import (
    QuoteContactSnapshot,
    QuoteFrameSnapshot,
    QuoteInDB,
    QuoteWallSnapshot,
)
from app.models.user import UserInDB
from app.modules import catalog
from app.repositories.design_repository import DesignRepository
from app.repositories.photo_repository import PhotoRepository
from app.repositories.quote_repository import DuplicateQuoteError, QuoteRepository
from app.schemas.quote import (
    QuoteDetailResponse,
    QuoteFrameInput,
    QuotePrepareInput,
    QuotePrepareResponse,
)
from app.services.image_processing_service import ImageProcessingService
from app.services.quote_report_service import QuoteReportService
from app.services.whatsapp_service import WhatsAppService
from app.storage import ObjectStorage

logger = logging.getLogger("moonlight_studio.quote_service")

# File extension for each accepted preview type (the key and the download name use it).
PREVIEW_EXTENSIONS: dict[str, str] = {
    "image/png": "png",
    "image/webp": "webp",
    "image/jpeg": "jpg",
}

# A retried request with the same Idempotency-Key gets its quote back for this long.
IDEMPOTENCY_WINDOW = timedelta(minutes=10)
# Saved wall sizes are floats: compare to this tolerance (inches).
WALL_TOLERANCE_IN = 0.01


def frame_dimensions(frame: QuoteFrameInput) -> tuple[float, float, float, float, float]:
    """(opening_w, opening_h, outer_w, outer_h, profile) in inches, as hung.

    Same formula as the planner (frontend frameGeometry): opening + 2 × (mount + moulding).
    Sizes and finishes are validated catalog IDs, so there is no fallback size.
    """
    size = catalog.get_frame_size(frame.size_id)
    if size is None:  # pragma: no cover - rejected by schema validation
        raise ValueError("unknown frame size")
    opening_w, opening_h = size.oriented(frame.orientation)
    profile = catalog.profile_inches(frame.finish_id)
    mat = frame.mount.margin_in if frame.mount.enabled else 0.0
    outer_w, outer_h = catalog.outer_size(opening_w, opening_h, profile, mat, mat, mat, mat)
    return opening_w, opening_h, round(outer_w, 2), round(outer_h, 2), profile


class QuoteService:
    """Service handling quotation preparation, validation, R2 upload, and retrieval."""

    def __init__(
        self,
        quote_repo: QuoteRepository,
        photo_repo: PhotoRepository,
        r2_storage: ObjectStorage,
        whatsapp_service: WhatsAppService | None = None,
        report_service: QuoteReportService | None = None,
        design_repo: DesignRepository | None = None,
    ) -> None:
        self.quote_repo = quote_repo
        self.photo_repo = photo_repo
        self.design_repo = design_repo
        self.r2_storage = r2_storage
        self.whatsapp_service = whatsapp_service or WhatsAppService()
        self.report_service = report_service or QuoteReportService()

    @staticmethod
    def _fingerprint(design_input: QuotePrepareInput) -> str:
        """Hash of the design payload, so a key can't be replayed with a different design."""
        canonical = design_input.model_dump_json(by_alias=True, exclude_none=False)
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def _check_saved_design(
        self, current_user: UserInDB, design_input: QuotePrepareInput
    ) -> None:
        """The quote must describe the design that is saved, and that design must be the user's.

        When `designId` is given: it has to exist, belong to the caller, and its current version
        must match what is being quoted (wall, layout style, and every frame's size, finish,
        mount, orientation and photo). Otherwise the report could show a design that isn't the
        saved one, so the caller is told to save first.
        """
        if not design_input.design_id or self.design_repo is None:
            return
        design = await self.design_repo.get_design_by_id(design_input.design_id)
        if design is None:
            raise ResourceNotFoundException(
                message="That design was not found. Save it again before requesting a quote.",
                field="designId",
            )
        if str(design.user_id) != str(current_user.id):
            raise ForbiddenException(
                message="You do not have permission to use this design.", field="designId"
            )
        version = (
            await self.design_repo.get_version_by_id(design.current_version_id)
            if design.current_version_id
            else None
        )

        def stale() -> ValidationException:
            return ValidationException(
                message="This design has unsaved changes. Save it, then request the quote.",
                details=[{"field": "designId", "issue": "Design differs from the saved version"}],
            )

        if version is None or len(version.items) != len(design_input.frames):
            raise stale()
        wall = design.wall
        if (
            abs(wall.width_inches - design_input.wall.width_in) > WALL_TOLERANCE_IN
            or abs(wall.height_inches - design_input.wall.height_in) > WALL_TOLERANCE_IN
            or (wall.paint_id or None) != (design_input.wall.paint_id or None)
        ):
            raise stale()
        saved_style = catalog.normalize_layout(version.layout_type)
        if saved_style != catalog.normalize_layout(design_input.layout.style):
            raise stale()

        saved = {item.item_id: item for item in version.items}
        for frame in design_input.frames:
            item = saved.get(frame.id)
            if item is None:
                raise stale()
            photo = frame.photo
            quoted_photo = (
                photo.photo_id if photo and photo.kind == "upload" else None,
                photo.sample_id if photo and photo.kind == "sample" else None,
            )
            mat = item.matting
            if (
                item.size_id != frame.size_id
                or item.finish_id != frame.finish_id
                or item.orientation != frame.orientation
                or bool(mat.enabled) != bool(frame.mount.enabled)
                or (mat.color_id or None) != (frame.mount.colour_id or None)
                or abs(mat.top_inches - frame.mount.margin_in) > WALL_TOLERANCE_IN
                or (item.photo_id or None, item.sample_id or None) != quoted_photo
            ):
                raise stale()

    def _build_response(self, quote: QuoteInDB, raw_share_token: str) -> QuotePrepareResponse:
        """WhatsApp and share links for a stored quote (same for a fresh or a retried request)."""
        report_url = f"{get_settings().PUBLIC_APP_URL}/q/{raw_share_token}"
        message = self.whatsapp_service.build_quote_message(
            quote_reference=quote.quote_reference,
            wall_width=quote.wall.width_inches,
            wall_height=quote.wall.height_inches,
            display_unit=quote.wall.display_unit,
            arrangement_style=quote.layout_style,
            frame_count=len(quote.frames),
            finish_summary=self.whatsapp_service.format_finish_summary(
                [f.finish_id for f in quote.frames]
            ),
            report_url=report_url,
            customer_name=quote.customer.full_name,
            customer_mobile=quote.customer.phone,
            customer_email=quote.customer.email,
        )
        return QuotePrepareResponse(
            quote_id=quote.quote_reference,
            status=quote.status,
            whatsapp_url=self.whatsapp_service.generate_whatsapp_url(message),
            report_url=report_url,
            expires_at=quote.expires_at,
        )

    async def _replay(self, existing: QuoteInDB, fingerprint: str) -> QuotePrepareResponse:
        """A retry of a request that already created a quote: return it, don't create another.

        Only the hash of the share token is stored, so the link is re-issued with a fresh token
        (the first response never reached the client, or a second tab asked again).
        """
        if existing.request_fingerprint != fingerprint:
            raise IdempotencyConflictException(
                "This request key was already used for a different design. Please try again."
            )
        created = (
            existing.created_at
            if existing.created_at.tzinfo
            else existing.created_at.replace(tzinfo=UTC)
        )
        if datetime.now(UTC) - created > IDEMPOTENCY_WINDOW:
            raise IdempotencyConflictException(
                "This request key has expired. Please start the quote request again."
            )
        raw_share_token = generate_secure_token(32)
        await self.quote_repo.replace_share_token(
            str(existing.id), hash_token(raw_share_token), raw_share_token[:8]
        )
        return self._build_response(existing, raw_share_token)

    async def validate_preview_image(self, file_bytes: bytes) -> tuple[str, int, int]:
        """Validate preview image format, size, and dimensions using Pillow."""
        if len(file_bytes) == 0:
            raise ValidationException(
                message="Preview image file is empty.",
                details=[{"field": "file", "issue": "File size is 0 bytes"}],
            )

        max_mb = get_settings().QUOTE_PREVIEW_MAX_MB
        if len(file_bytes) > max_mb * 1024 * 1024:
            raise ValidationException(
                message=f"Preview image is larger than {max_mb} MB.",
                details=[{"field": "file", "issue": f"Image exceeds {max_mb} MB"}],
            )

        mime_type = ImageProcessingService.sniff_mime_type(file_bytes)
        if mime_type not in ("image/png", "image/webp", "image/jpeg"):
            raise ValidationException(
                message="Preview image must be a valid PNG, WebP, or JPEG image.",
                details=[{"field": "file", "issue": "Unsupported image signature"}],
            )

        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                img.verify()
            with Image.open(io.BytesIO(file_bytes)) as img:
                w, h = img.size
                if w < 100 or h < 100:
                    raise ValidationException(
                        message="Preview image dimensions are too small for quotation review.",
                        details=[
                            {
                                "field": "file",
                                "issue": f"Dimensions ({w}x{h}) below minimum 100x100px",
                            }
                        ],
                    )
                if w > 8192 or h > 8192:
                    raise ValidationException(
                        message="Preview image exceeds maximum resolution of 8192x8192px.",
                        details=[
                            {
                                "field": "file",
                                "issue": f"Dimensions ({w}x{h}) exceed 8192px limit",
                            }
                        ],
                    )
                return mime_type, w, h
        except ValidationException:
            raise
        except Exception as exc:
            logger.warning("Corrupt or invalid preview image submitted: %s", exc)
            raise ValidationException(
                message="Corrupt or unreadable preview image.",
                details=[{"field": "file", "issue": "Image data is corrupt"}],
            ) from exc

    async def prepare_quote(
        self,
        current_user: UserInDB,
        design_input: QuotePrepareInput,
        preview_bytes: bytes,
        idempotency_key: str | None = None,
    ) -> QuotePrepareResponse:
        """Capture Memory Wall design, upload preview to R2, and return WhatsApp URL."""
        settings = get_settings()

        # 0. A retry of an earlier request returns that quote instead of creating another.
        fingerprint = self._fingerprint(design_input)
        if idempotency_key:
            existing = await self.quote_repo.get_by_idempotency_key(
                str(current_user.id), idempotency_key
            )
            if existing:
                return await self._replay(existing, fingerprint)
        await self._check_saved_design(current_user, design_input)

        # 1. Authoritative customer profile snapshot from DB (never trust request body)
        customer_snapshot = QuoteContactSnapshot(
            full_name=current_user.full_name,
            email=current_user.email,
            phone=current_user.phone,
        )

        # 2. Frame specifications (catalog-resolved) and photo ownership
        frame_snapshots: list[QuoteFrameSnapshot] = []
        finish_ids: list[str] = []

        for idx, frame in enumerate(design_input.frames, start=1):
            finish_ids.append(frame.finish_id)

            # Security: If referencing user-uploaded photo asset, enforce user ownership
            photo_kind = "none"
            photo_id = None
            sample_id = None
            photo_name = None

            if frame.photo:
                photo_kind = frame.photo.kind
                if frame.photo.kind == "upload" and frame.photo.photo_id:
                    # Check ownership in photo repository
                    user_photo = await self.photo_repo.get_by_id(frame.photo.photo_id)
                    if not user_photo or str(user_photo.user_id) != str(current_user.id):
                        raise ForbiddenException(
                            message=(
                                f"You do not have permission to use photo asset "
                                f"'{frame.photo.photo_id}'."
                            ),
                            field="photo_id",
                        )
                    photo_id = str(user_photo.id)
                    photo_name = user_photo.original_filename
                elif frame.photo.kind == "sample" and frame.photo.sample_id:
                    sample_id = frame.photo.sample_id
                    photo_name = frame.photo.name or f"Sample {sample_id}"

            opening_w, opening_h, outer_w, outer_h, profile = frame_dimensions(frame)
            # No colour chosen → the planner default (Museum White).
            mount_colour = (
                catalog.get_mount_colour(frame.mount.colour_id) or catalog.MOUNT_COLOURS[0]
            )

            frame_snapshots.append(
                QuoteFrameSnapshot(
                    item_id=frame.id,
                    frame_number=idx,
                    size_id=frame.size_id,
                    orientation=frame.orientation,
                    finish_id=frame.finish_id,
                    finish_name=catalog.finish_label(frame.finish_id),
                    width_inches=outer_w,
                    height_inches=outer_h,
                    opening_width_inches=opening_w,
                    opening_height_inches=opening_h,
                    profile_inches=profile,
                    position_x_inches=frame.position_x_in or 0.0,
                    position_y_inches=frame.position_y_in or 0.0,
                    mount_enabled=frame.mount.enabled,
                    mount_color_id=mount_colour.id,
                    mount_color_name=mount_colour.label,
                    mount_margin_inches=frame.mount.margin_in,
                    photo_kind=photo_kind,
                    photo_id=photo_id,
                    sample_id=sample_id,
                    photo_name=photo_name,
                )
            )

        # 3. Validate preview image and sniff MIME type
        mime_type, img_w, img_h = await self.validate_preview_image(preview_bytes)

        # 5. Generate unique quote reference (MQ-YYYY-XXXX) and tokens
        quote_reference = await self.quote_repo.get_next_quote_reference()
        raw_share_token = generate_secure_token(32)
        share_token_hash = hash_token(raw_share_token)
        share_token_prefix = raw_share_token[:8]
        expires_at = datetime.now(UTC) + timedelta(days=settings.QUOTE_SHARE_EXPIRY_DAYS)

        # 6. Upload preview image to Cloudflare R2
        ext = PREVIEW_EXTENSIONS[mime_type]
        preview_key = f"quotes/{current_user.id}/{quote_reference}/preview.{ext}"

        await self.r2_storage.put_object(
            key=preview_key,
            data=preview_bytes,
            content_type=mime_type,
            metadata={
                "quote_reference": quote_reference,
                "user_id": str(current_user.id),
                "width": str(img_w),
                "height": str(img_h),
            },
        )

        # 7. Construct and persist immutable QuoteInDB document in MongoDB
        wall_snapshot = QuoteWallSnapshot(
            width_inches=design_input.wall.width_in,
            height_inches=design_input.wall.height_in,
            paint_id=design_input.wall.paint_id,
            color_hex=design_input.effective_color_hex,
            texture=design_input.wall.texture,
            display_unit=design_input.effective_display_unit,
            has_sofa=design_input.effective_has_sofa,
        )

        quote_doc = QuoteInDB(
            quote_reference=quote_reference,
            user_id=str(current_user.id),
            customer=customer_snapshot,
            design_id=design_input.design_id,
            design_title=design_input.title or "Memory Wall Design",
            layout_style=design_input.layout.style,
            wall=wall_snapshot,
            frames=frame_snapshots,
            preview_image_key=preview_key,
            preview_image_content_type=mime_type,
            share_token_hash=share_token_hash,
            share_token_prefix=share_token_prefix,
            status="draft",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint if idempotency_key else None,
            expires_at=expires_at,
        )

        try:
            await self.quote_repo.create(quote_doc)
            logger.info(
                "Created quote %s for user %s with share token prefix %s",
                quote_reference,
                current_user.id,
                share_token_prefix,
            )
        except DuplicateQuoteError:
            # A concurrent request with this key won the race: drop our upload, return its quote.
            await self.r2_storage.delete_object(preview_key)
            winner = await self.quote_repo.get_by_idempotency_key(
                str(current_user.id), idempotency_key or ""
            )
            if winner is None:  # pragma: no cover - the unique index just said it exists
                raise
            return await self._replay(winner, fingerprint)
        except Exception as exc:
            # Rollback: Clean up uploaded R2 preview if database persistence fails
            logger.error(
                "MongoDB persistence failed for quote %s; cleaning up R2 key %s: %s",
                quote_reference,
                preview_key,
                exc,
            )
            await self.r2_storage.delete_object(preview_key)
            raise

        # 8. WhatsApp message and Click-to-Chat URL for the customer to review and send
        return self._build_response(quote_doc, raw_share_token)

    async def get_quote_by_id(self, quote_id: str, current_user: UserInDB) -> QuoteDetailResponse:
        """Authorized retrieval of quote by ID for the owner customer."""
        quote = await self.quote_repo.get_by_id(quote_id)
        if not quote:
            raise ResourceNotFoundException(
                message=f"Quote record '{quote_id}' was not found.",
                field="id",
            )

        # IDOR protection: only owner (or admin) can view authorized quote
        if quote.user_id != str(current_user.id) and current_user.role != "admin":
            raise ResourceNotFoundException(
                message=f"Quote record '{quote_id}' was not found.",
                field="id",
            )

        wall_size = catalog.format_wall_size(
            quote.wall.width_inches, quote.wall.height_inches, quote.wall.display_unit
        )
        finish_ids = [f.finish_id for f in quote.frames]
        finish_summary = self.whatsapp_service.format_finish_summary(finish_ids)
        frame_specs = self.report_service.build_frame_spec_list(quote)

        # Generate presigned or streaming preview URL
        preview_url = await self.r2_storage.generate_presigned_url(quote.preview_image_key)

        return QuoteDetailResponse(
            quote_id=quote.quote_reference,
            status=quote.status,
            design_title=quote.design_title,
            layout_style=self.whatsapp_service.format_style_label(quote.layout_style),
            wall_size=wall_size,
            frame_count=len(quote.frames),
            finish_summary=finish_summary,
            report_url=None,
            preview_url=preview_url,
            customer_name=quote.customer.full_name,
            customer_phone=quote.customer.phone,
            customer_email=quote.customer.email,
            frames=frame_specs,
            expires_at=quote.expires_at,
            created_at=quote.created_at,
        )

    async def get_quote_by_share_token(self, raw_token: str) -> tuple[QuoteInDB, str]:
        """Validate share token, check expiration, and resolve public preview URL."""
        settings = get_settings()
        token_hash = hash_token(raw_token)
        quote = await self.quote_repo.get_by_share_token_hash(token_hash)

        if not quote:
            raise ResourceNotFoundException(
                message="This design report was not found or the share link is invalid.",
                field="token",
            )

        # Check expiration
        now = datetime.now(UTC)
        quote_expires_at = (
            quote.expires_at if quote.expires_at.tzinfo else quote.expires_at.replace(tzinfo=UTC)
        )
        if now > quote_expires_at:
            raise ResourceNotFoundException(
                message="This design report share link has expired.",
                field="token",
            )

        # Secure preview image URL for public viewer (via streaming endpoint without auth)
        preview_url = f"{settings.API_V1_STR}/quotes/share/{raw_token}/preview"

        return quote, preview_url
