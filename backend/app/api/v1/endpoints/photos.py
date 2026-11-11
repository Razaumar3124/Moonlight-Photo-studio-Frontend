from fastapi import (
    APIRouter,
    File,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)

from app.api.dependencies import (
    CurrentUserDep,
    OptionalCurrentUserDep,
    PhotoServiceDep,
)
from app.core.exceptions import ValidationException
from app.schemas.common import ApiErrorResponse
from app.schemas.photo import PhotosListResponse, PhotoUploadResponse

router = APIRouter(prefix="/photos", tags=["Photos"])


@router.post(
    "/upload",
    response_model=PhotoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ApiErrorResponse,
            "description": "Invalid image header or unreadable file",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Missing or invalid Bearer access token",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ApiErrorResponse,
            "description": "File exceeds size limits or fails dimension validation",
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ApiErrorResponse,
            "description": "Hourly photo upload rate limit exceeded",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ApiErrorResponse,
            "description": "Cloudflare R2 or database unavailable",
        },
    },
    summary="Upload and process an image",
    description=(
        "Validates image format and magic bytes, auto-rotates via EXIF, "
        "generates WebP previews and thumbnails, uploads to Cloudflare R2, "
        "and saves metadata in MongoDB."
    ),
)
async def upload_photo(
    request: Request,
    photo_service: PhotoServiceDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(description="Binary photograph (JPEG, PNG, or WebP)"),
) -> PhotoUploadResponse:
    """EP-PHOTO-01: User photograph upload."""
    if not file or not file.filename:
        raise ValidationException(
            message="No file uploaded. Please attach a valid photo.",
            details=[{"field": "file", "issue": "Missing file payload"}],
        )

    file_bytes = await file.read()
    client_ip = request.client.host if request.client else None

    return await photo_service.upload_photo(
        user_id=current_user.id,
        filename=file.filename,
        file_bytes=file_bytes,
        declared_content_type=file.content_type,
        client_ip=client_ip,
    )


@router.get(
    "",
    response_model=PhotosListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Missing or invalid Bearer access token",
        },
    },
    summary="List authenticated user's photographs",
    description=(
        "Returns a paginated list of active photos owned by the authenticated "
        "user, including natural dimensions and signed thumbnail URLs."
    ),
)
async def list_user_photos(
    photo_service: PhotoServiceDep,
    current_user: CurrentUserDep,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
) -> PhotosListResponse:
    """EP-PHOTO-02: List user photographs."""
    return await photo_service.list_user_photos(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{id}/thumbnail",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Authentication required",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ApiErrorResponse,
            "description": "Expired signature or unauthorized access",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ApiErrorResponse,
            "description": "Photograph not found",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ApiErrorResponse,
            "description": "Storage service unavailable",
        },
    },
    summary="Retrieve secure photo thumbnail",
    description=(
        "Streams the 300px WebP thumbnail from Cloudflare R2. "
        "Verified via short-lived HMAC signature parameter (?sig=...&exp=...) "
        "for direct HTML <img> loading, or via Bearer authorization header."
    ),
)
async def get_photo_thumbnail(
    id: str,
    photo_service: PhotoServiceDep,
    optional_user: OptionalCurrentUserDep,
    sig: str | None = Query(default=None, description="Short-lived HMAC signature"),
    exp: int | None = Query(default=None, description="Signature expiration epoch timestamp"),
) -> Response:
    """EP-PHOTO-03: Stream photo thumbnail."""
    requester_id = optional_user.id if optional_user else None
    content, content_type = await photo_service.get_photo_media(
        photo_id=id,
        kind="thumbnail",
        requester_user_id=requester_id,
        sig=sig,
        exp=exp,
    )
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "Content-Disposition": f'inline; filename="{id}-thumb.webp"',
        },
    )


@router.get(
    "/{id}/preview",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Authentication required",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ApiErrorResponse,
            "description": "Expired signature or unauthorized access",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ApiErrorResponse,
            "description": "Photograph not found",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ApiErrorResponse,
            "description": "Storage service unavailable",
        },
    },
    summary="Retrieve secure photo preview",
    description=(
        "Streams the 1600px WebP preview from Cloudflare R2. "
        "Verified via short-lived HMAC signature parameter (?sig=...&exp=...) "
        "or via Bearer authorization header."
    ),
)
async def get_photo_preview(
    id: str,
    photo_service: PhotoServiceDep,
    optional_user: OptionalCurrentUserDep,
    sig: str | None = Query(default=None, description="Short-lived HMAC signature"),
    exp: int | None = Query(default=None, description="Signature expiration epoch timestamp"),
) -> Response:
    """EP-PHOTO-04: Stream photo preview."""
    requester_id = optional_user.id if optional_user else None
    content, content_type = await photo_service.get_photo_media(
        photo_id=id,
        kind="preview",
        requester_user_id=requester_id,
        sig=sig,
        exp=exp,
    )
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "Content-Disposition": f'inline; filename="{id}-preview.webp"',
        },
    )


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Authentication required",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ApiErrorResponse,
            "description": "Attempting to delete unowned photograph (IDOR protection)",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ApiErrorResponse,
            "description": "Photograph not found",
        },
    },
    summary="Delete an owned photograph",
    description=(
        "Soft-deletes photograph metadata in MongoDB and deletes corresponding "
        "objects from Cloudflare R2 storage bucket."
    ),
)
async def delete_photo(
    id: str,
    photo_service: PhotoServiceDep,
    current_user: CurrentUserDep,
) -> None:
    """EP-PHOTO-05: Delete owned photograph."""
    await photo_service.delete_photo(
        photo_id=id,
        user_id=current_user.id,
    )
