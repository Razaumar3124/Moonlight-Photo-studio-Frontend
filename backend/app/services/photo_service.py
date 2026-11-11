import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

from bson import ObjectId

from app.core.config import get_settings
from app.core.exceptions import (
    ForbiddenException,
    RateLimitExceededException,
    ResourceNotFoundException,
    StorageUnavailableException,
)
from app.core.security import generate_photo_signature, verify_photo_signature
from app.models.photo import PhotoInDB
from app.repositories.photo_repository import PhotoRepository
from app.schemas.photo import (
    PhotosListResponse,
    PhotoSummaryOut,
    PhotoUploadResponse,
)
from app.services.image_processing_service import ImageProcessingService
from app.services.rate_limiter import rate_limiter
from app.storage.r2_storage import R2Storage

logger = logging.getLogger("saf_studio.photo_service")


class PhotoService:
    """Domain business service managing photograph uploads, R2 storage, access, and deletion."""

    def __init__(
        self,
        photo_repo: PhotoRepository,
        image_service: ImageProcessingService,
        r2_storage: R2Storage,
    ) -> None:
        self.photo_repo = photo_repo
        self.image_service = image_service
        self.r2_storage = r2_storage

    def _generate_signed_urls(self, photo_id: str) -> tuple[str, str]:
        """Generate short-lived HMAC signed paths for thumbnail and preview."""
        settings = get_settings()
        expires_at = int(
            (
                datetime.now(UTC) + timedelta(seconds=settings.PHOTO_SIGNED_URL_EXPIRATION_SECONDS)
            ).timestamp()
        )
        thumb_sig = generate_photo_signature(photo_id, "thumbnail", expires_at)
        prev_sig = generate_photo_signature(photo_id, "preview", expires_at)

        thumbnail_url = f"/api/v1/photos/{photo_id}/thumbnail?sig={thumb_sig}&exp={expires_at}"
        preview_url = f"/api/v1/photos/{photo_id}/preview?sig={prev_sig}&exp={expires_at}"
        return thumbnail_url, preview_url

    async def upload_photo(
        self,
        user_id: str,
        filename: str,
        file_bytes: bytes,
        declared_content_type: str | None = None,
        client_ip: str | None = None,
    ) -> PhotoUploadResponse:
        """Process and store a user uploaded photograph in Cloudflare R2 and MongoDB."""
        settings = get_settings()

        # 1. Rate limiting on photo uploads (30 uploads / hour per user)
        rate_key = f"photo_upload:{user_id}"
        if not rate_limiter.is_allowed(
            rate_key,
            max_attempts=settings.RATE_LIMIT_PHOTO_UPLOAD_MAX_ATTEMPTS,
            window_seconds=settings.RATE_LIMIT_PHOTO_UPLOAD_WINDOW_SECONDS,
        ):
            raise RateLimitExceededException(
                "Upload rate limit exceeded. You may upload up to 30 photos per hour."
            )

        # 2. Sanitize and trim filename
        clean_filename = filename.strip()[:120] if filename else "untitled.jpg"

        # 3. Validate and process image via ImageProcessingService (Pillow)
        processed = await self.image_service.process_image(
            file_bytes,
            declared_content_type=declared_content_type,
        )

        # 4. Generate persistent storage keys with secure random ObjectId
        photo_id = str(ObjectId())
        ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
        orig_ext = ext_map.get(processed.mime_type, ".jpg")

        orig_key = f"users/{user_id}/photos/{photo_id}/original{orig_ext}"
        prev_key = f"users/{user_id}/photos/{photo_id}/preview.webp"
        thumb_key = f"users/{user_id}/photos/{photo_id}/thumbnail.webp"

        uploaded_keys: list[str] = []
        try:
            # 5. Upload original image to Cloudflare R2
            await self.r2_storage.put_object(
                key=orig_key,
                data=processed.original_bytes,
                content_type=processed.mime_type,
                metadata={"user_id": user_id, "photo_id": photo_id},
            )
            uploaded_keys.append(orig_key)

            # 6. Upload 1600px preview WebP to Cloudflare R2
            await self.r2_storage.put_object(
                key=prev_key,
                data=processed.preview_bytes,
                content_type="image/webp",
                metadata={"user_id": user_id, "photo_id": photo_id, "type": "preview"},
            )
            uploaded_keys.append(prev_key)

            # 7. Upload 300px thumbnail WebP to Cloudflare R2
            await self.r2_storage.put_object(
                key=thumb_key,
                data=processed.thumbnail_bytes,
                content_type="image/webp",
                metadata={"user_id": user_id, "photo_id": photo_id, "type": "thumbnail"},
            )
            uploaded_keys.append(thumb_key)

        except Exception as exc:
            logger.error("R2 upload failure, rolling back uploaded objects: %s", exc)
            if uploaded_keys:
                await self.r2_storage.delete_objects(uploaded_keys)
            raise StorageUnavailableException(
                issue=f"Failed to store photograph in Cloudflare R2: {exc}"
            ) from exc

        # 8. Save photograph metadata document in MongoDB
        now = datetime.now(UTC)
        photo_doc = PhotoInDB(
            id=photo_id,
            user_id=user_id,
            original_filename=clean_filename,
            storage_key=orig_key,
            thumbnail_key=thumb_key,
            preview_key=prev_key,
            storage_provider="cloudflare_r2",
            bucket=self.r2_storage.bucket_name,
            mime_type=processed.mime_type,
            file_size_bytes=processed.file_size_bytes,
            width_px=processed.natural_width,
            height_px=processed.natural_height,
            aspect_ratio=processed.aspect_ratio,
            suggested_orientation=processed.suggested_orientation,
            status="ready",
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )

        try:
            await self.photo_repo.create(photo_doc)
        except Exception as exc:
            logger.error("MongoDB metadata persistence failed, rolling back R2 objects: %s", exc)
            await self.r2_storage.delete_objects(uploaded_keys)
            raise

        # 9. Generate secure short-lived URLs for direct <img src> rendering
        thumbnail_url, preview_url = self._generate_signed_urls(photo_id)

        return PhotoUploadResponse(
            id=photo_id,
            user_id=user_id,
            original_filename=clean_filename,
            file_size_bytes=processed.file_size_bytes,
            mime_type=processed.mime_type,
            width_px=processed.natural_width,
            height_px=processed.natural_height,
            aspect_ratio=processed.aspect_ratio,
            suggested_orientation=processed.suggested_orientation,
            thumbnail_url=thumbnail_url,
            preview_url=preview_url,
            created_at=now.isoformat(),
        )

    async def list_user_photos(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> PhotosListResponse:
        """List authenticated user's uploaded photographs."""
        photos, total = await self.photo_repo.list_by_user(
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

        items: list[PhotoSummaryOut] = []
        for p in photos:
            thumb_url, _ = self._generate_signed_urls(p.id)
            items.append(
                PhotoSummaryOut(
                    id=p.id,
                    original_filename=p.original_filename,
                    width_px=p.width_px,
                    height_px=p.height_px,
                    aspect_ratio=p.aspect_ratio,
                    thumbnail_url=thumb_url,
                    created_at=p.created_at.isoformat(),
                )
            )

        return PhotosListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_photo_media(
        self,
        photo_id: str,
        kind: Literal["thumbnail", "preview"],
        requester_user_id: str | None = None,
        sig: str | None = None,
        exp: int | None = None,
    ) -> tuple[bytes, str]:
        """Verify access and stream photograph media from Cloudflare R2."""
        if not ObjectId.is_valid(photo_id):
            raise ResourceNotFoundException("Photograph was not found.", field="id")

        photo = await self.photo_repo.get_by_id(photo_id, include_deleted=False)
        if not photo or photo.is_deleted:
            raise ResourceNotFoundException(
                "Photograph was not found or has been removed.", field="id"
            )

        # Access verification: HMAC signed URL OR Authenticated Owner Bearer token
        authorized = False
        if sig and exp is not None:
            if verify_photo_signature(photo_id, kind, sig, exp):
                authorized = True
            else:
                raise ForbiddenException("Photo access link has expired or signature is invalid.")
        elif requester_user_id:
            if str(photo.user_id) == str(requester_user_id):
                authorized = True
            else:
                raise ForbiddenException("You do not have permission to view this photograph.")

        if not authorized:
            raise ForbiddenException("Authentication or valid signature required to view photo.")

        # Determine target R2 key
        target_key = photo.thumbnail_key if kind == "thumbnail" else photo.preview_key

        return await self.r2_storage.get_object(target_key)

    async def delete_photo(self, photo_id: str, user_id: str) -> None:
        """Securely delete user's photograph from Cloudflare R2 and MongoDB."""
        if not ObjectId.is_valid(photo_id):
            raise ResourceNotFoundException("Photograph was not found.", field="id")

        photo = await self.photo_repo.get_by_id(photo_id, include_deleted=False)
        if not photo or photo.is_deleted:
            raise ResourceNotFoundException("Photograph was not found.", field="id")

        # BOLA/IDOR protection
        if str(photo.user_id) != str(user_id):
            raise ForbiddenException("You do not have permission to delete this photograph.")

        # Soft delete in database first
        await self.photo_repo.soft_delete(photo_id, user_id)

        # Remove R2 objects asynchronously
        keys_to_delete = [photo.storage_key, photo.preview_key, photo.thumbnail_key]
        await self.r2_storage.delete_objects(keys_to_delete)
        logger.info("Deleted photo %s and its R2 storage assets", photo_id)
