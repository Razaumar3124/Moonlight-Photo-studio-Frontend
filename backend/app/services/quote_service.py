"""Core Quote Service orchestrating design capture, validation, R2 storage, and WhatsApp linking."""

import io
import logging
from datetime import UTC, datetime, timedelta

from PIL import Image

from app.core.config import get_settings
from app.core.exceptions import (
    ForbiddenException,
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
from app.repositories.photo_repository import PhotoRepository
from app.repositories.quote_repository import QuoteRepository
from app.schemas.quote import (
    QuoteDetailResponse,
    QuotePrepareInput,
    QuotePrepareResponse,
)
from app.services.image_processing_service import ImageProcessingService
from app.services.quote_report_service import QuoteReportService
from app.services.whatsapp_service import WhatsAppService
from app.storage.r2_storage import R2Storage

logger = logging.getLogger("saf_studio.quote_service")

# Approximate profile widths in inches for standard wood mouldings
FRAME_PROFILE_WIDTHS: dict[str, float] = {
    "natural-oak": 1.0,
    "dark-walnut": 1.0,
    "matte-black": 0.75,
    "warm-metallic": 0.75,
    "white-ash": 1.0,
    "raw-pine": 1.0,
}

STANDARD_SIZES: dict[str, tuple[float, float]] = {
    "8x10": (8.0, 10.0),
    "10x12": (10.0, 12.0),
    "11x14": (11.0, 14.0),
    "12x16": (12.0, 16.0),
    "16x20": (16.0, 20.0),
    "20x24": (20.0, 24.0),
    "24x36": (24.0, 36.0),
}


class QuoteService:
    """Service handling quotation preparation, validation, R2 upload, and retrieval."""

    def __init__(
        self,
        quote_repo: QuoteRepository,
        photo_repo: PhotoRepository,
        r2_storage: R2Storage,
        whatsapp_service: WhatsAppService | None = None,
        report_service: QuoteReportService | None = None,
    ) -> None:
        self.quote_repo = quote_repo
        self.photo_repo = photo_repo
        self.r2_storage = r2_storage
        self.whatsapp_service = whatsapp_service or WhatsAppService()
        self.report_service = report_service or QuoteReportService()

    @staticmethod
    def _parse_size(size_id: str) -> tuple[float, float]:
        """Resolve frame opening dimensions (width, height) in inches."""
        cleaned = size_id.lower().replace(" ", "").replace("x", "×")
        for key, dims in STANDARD_SIZES.items():
            if key == size_id.lower() or key.replace("x", "×") == cleaned:
                return dims
        # Try parse WxH
        parts = cleaned.split("×")
        if len(parts) == 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                pass
        return 12.0, 16.0  # Fallback standard size

    def _calculate_outer_dimensions(
        self,
        size_id: str,
        orientation: str,
        finish_id: str,
        mount_enabled: bool,
        mount_margin: float,
    ) -> tuple[float, float]:
        """Compute outer dimensions of the frame including mat and moulding."""
        w, h = self._parse_size(size_id)
        if orientation == "landscape":
            w, h = h, w

        profile_in = FRAME_PROFILE_WIDTHS.get(finish_id, 1.0)
        mat_in = mount_margin if mount_enabled else 0.0

        outer_w = w + 2 * (mat_in + profile_in)
        outer_h = h + 2 * (mat_in + profile_in)
        return round(outer_w, 2), round(outer_h, 2)

    async def validate_preview_image(self, file_bytes: bytes) -> tuple[str, int, int]:
        """Validate preview image format, size, and dimensions using Pillow."""
        if len(file_bytes) == 0:
            raise ValidationException(
                message="Preview image file is empty.",
                details=[{"field": "preview_image", "issue": "File size is 0 bytes"}],
            )

        if len(file_bytes) > 15 * 1024 * 1024:
            raise ValidationException(
                message="Preview image is larger than 15 MB limit.",
                details=[
                    {
                        "field": "preview_image",
                        "issue": f"Image size ({len(file_bytes)} bytes) exceeds 15 MB",
                    }
                ],
            )

        mime_type = ImageProcessingService.sniff_mime_type(file_bytes)
        if mime_type not in ("image/png", "image/webp", "image/jpeg"):
            raise ValidationException(
                message="Preview image must be a valid PNG, WebP, or JPEG image.",
                details=[{"field": "preview_image", "issue": "Unsupported image signature"}],
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
                                "field": "preview_image",
                                "issue": f"Dimensions ({w}x{h}) below minimum 100x100px",
                            }
                        ],
                    )
                if w > 8192 or h > 8192:
                    raise ValidationException(
                        message="Preview image exceeds maximum resolution of 8192x8192px.",
                        details=[
                            {
                                "field": "preview_image",
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
                details=[{"field": "preview_image", "issue": f"Decompression failed: {exc}"}],
            ) from exc

    async def prepare_quote(
        self,
        current_user: UserInDB,
        design_input: QuotePrepareInput,
        preview_bytes: bytes,
    ) -> QuotePrepareResponse:
        """Capture Memory Wall design, upload preview to R2, and return WhatsApp URL."""
        settings = get_settings()

        # 1. Authoritative customer profile snapshot from DB (never trust request body)
        customer_snapshot = QuoteContactSnapshot(
            full_name=current_user.full_name,
            email=current_user.email,
            phone=current_user.phone,
        )

        # 2. Validate wall dimensions and frame count
        if design_input.wall.width_in <= 0 or design_input.wall.height_in <= 0:
            raise ValidationException(
                message="Wall width and height must be positive numbers.",
                details=[{"field": "wall", "issue": "Invalid wall dimensions"}],
            )

        if not design_input.frames:
            raise ValidationException(
                message="At least one frame is required to request a quote.",
                details=[{"field": "frames", "issue": "Frames array cannot be empty"}],
            )

        # 3. Validate frame specifications and photo ownership
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
                elif frame.photo.kind == "sample":
                    sample_id = frame.photo.sample_id
                    photo_name = frame.photo.name or f"Sample {sample_id}"

            mount_enabled = frame.mount.enabled if frame.mount else True
            mount_margin = frame.mount.margin_in if frame.mount else 2.0
            finish_label = self.whatsapp_service.FINISH_LABELS.get(
                frame.finish_id, frame.finish_id.replace("-", " ").title()
            )

            outer_w, outer_h = self._calculate_outer_dimensions(
                size_id=frame.size_id,
                orientation=frame.orientation,
                finish_id=frame.finish_id,
                mount_enabled=mount_enabled,
                mount_margin=mount_margin,
            )

            frame_snapshots.append(
                QuoteFrameSnapshot(
                    item_id=frame.id,
                    frame_number=idx,
                    size_id=frame.size_id,
                    orientation=frame.orientation,
                    finish_id=frame.finish_id,
                    finish_name=finish_label,
                    width_inches=outer_w,
                    height_inches=outer_h,
                    position_x_inches=frame.position_x_in or 0.0,
                    position_y_inches=frame.position_y_in or 0.0,
                    mount_enabled=mount_enabled,
                    mount_color_name=frame.mount.colour_id if frame.mount else "Museum White",
                    mount_margin_inches=mount_margin,
                    photo_kind=photo_kind,
                    photo_id=photo_id,
                    sample_id=sample_id,
                    photo_name=photo_name,
                )
            )

        # 4. Validate preview image and sniff MIME type
        mime_type, img_w, img_h = await self.validate_preview_image(preview_bytes)

        # 5. Generate unique quote reference (SQ-YYYY-XXXX) and tokens
        quote_reference = await self.quote_repo.get_next_quote_reference()
        raw_share_token = generate_secure_token(32)
        share_token_hash = hash_token(raw_share_token)
        share_token_prefix = raw_share_token[:8]
        expires_at = datetime.now(UTC) + timedelta(days=settings.QUOTE_SHARE_EXPIRY_DAYS)

        # 6. Upload preview image to Cloudflare R2
        ext = "webp" if mime_type == "image/webp" else "png"
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
            color_hex=design_input.wall.color_hex,
            texture=design_input.wall.texture,
            display_unit=design_input.wall.display_unit,
            has_sofa=design_input.wall.has_sofa,
        )

        quote_doc = QuoteInDB(
            quote_reference=quote_reference,
            user_id=str(current_user.id),
            customer=customer_snapshot,
            design_id=design_input.design_id,
            design_title=design_input.title or "Memory Wall Design",
            layout_style=design_input.layout.style if design_input.layout else "grid",
            wall=wall_snapshot,
            frames=frame_snapshots,
            preview_image_key=preview_key,
            preview_image_content_type=mime_type,
            share_token_hash=share_token_hash,
            share_token_prefix=share_token_prefix,
            status="draft",
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

        # 8. Compose WhatsApp message and Click-to-Chat URL
        report_url = f"{settings.PUBLIC_APP_URL}/q/{raw_share_token}"
        finish_summary = self.whatsapp_service.format_finish_summary(finish_ids)

        whatsapp_message = self.whatsapp_service.build_quote_message(
            quote_reference=quote_reference,
            wall_width=design_input.wall.width_in,
            wall_height=design_input.wall.height_in,
            display_unit=design_input.wall.display_unit,
            arrangement_style=design_input.layout.style if design_input.layout else "grid",
            frame_count=len(design_input.frames),
            finish_summary=finish_summary,
            report_url=report_url,
            customer_name=current_user.full_name,
            customer_mobile=current_user.phone,
            customer_email=current_user.email,
        )

        whatsapp_url = self.whatsapp_service.generate_whatsapp_url(whatsapp_message)

        return QuotePrepareResponse(
            quote_id=quote_reference,
            status="draft",
            whatsapp_url=whatsapp_url,
            report_url=report_url,
            expires_at=expires_at,
        )

    async def get_quote_by_id(self, quote_id: str, current_user: UserInDB) -> QuoteDetailResponse:
        """Authorized retrieval of quote by ID for the owner customer."""
        settings = get_settings()
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

        unit = (
            "inches"
            if quote.wall.display_unit in ("in", "inch", "inches")
            else quote.wall.display_unit
        )
        wall_size = f"{quote.wall.width_inches:g} × {quote.wall.height_inches:g} {unit}"
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
            report_url=f"{settings.PUBLIC_APP_URL}/q/{quote.share_token_prefix}",
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
            quote.expires_at
            if quote.expires_at.tzinfo
            else quote.expires_at.replace(tzinfo=UTC)
        )
        if now > quote_expires_at:
            raise ResourceNotFoundException(
                message="This design report share link has expired.",
                field="token",
            )

        # Secure preview image URL for public viewer (via streaming endpoint without auth)
        preview_url = f"{settings.API_V1_STR}/quotes/share/{raw_token}/preview"

        return quote, preview_url
