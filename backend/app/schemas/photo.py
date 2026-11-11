from pydantic import BaseModel, ConfigDict, Field


class PhotoUploadResponse(BaseModel):
    """Response payload for EP-PHOTO-01 upload photograph endpoint."""

    id: str = Field(description="Unique photograph identifier")
    user_id: str = Field(description="Identifier of the photo owner")
    original_filename: str = Field(description="Client-supplied filename")
    file_size_bytes: int = Field(description="File size in bytes")
    mime_type: str = Field(description="Image MIME type (image/jpeg, image/png, image/webp)")
    width_px: int = Field(description="Natural image width in pixels after EXIF orientation")
    height_px: int = Field(description="Natural image height in pixels after EXIF orientation")
    aspect_ratio: float = Field(description="Width divided by height rounded to 4 decimals")
    suggested_orientation: str = Field(description="Orientation: portrait, landscape, or square")
    thumbnail_url: str = Field(description="Short-lived secure signed URL for 300px thumbnail")
    preview_url: str = Field(description="Short-lived secure signed URL for 1600px preview")
    created_at: str = Field(description="ISO-8601 UTC timestamp of creation")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "672cf3a9e4b0123456789def",
                "user_id": "672cf1a9e4b0123456789abc",
                "original_filename": "family-portrait.jpg",
                "file_size_bytes": 4194304,
                "mime_type": "image/jpeg",
                "width_px": 4000,
                "height_px": 3000,
                "aspect_ratio": 1.3333,
                "suggested_orientation": "landscape",
                "thumbnail_url": "/api/v1/photos/672cf3a9e4b0123456789def/thumbnail?sig=a1b2c3d4",
                "preview_url": "/api/v1/photos/672cf3a9e4b0123456789def/preview?sig=e5f6a7b8",
                "created_at": "2026-11-07T12:05:00.000Z",
            }
        },
    )


class PhotoSummaryOut(BaseModel):
    """Compact photograph representation for gallery trays and EP-PHOTO-02 list endpoint."""

    id: str = Field(description="Unique photograph identifier")
    original_filename: str = Field(description="Client-supplied filename")
    width_px: int = Field(description="Natural image width in pixels")
    height_px: int = Field(description="Natural image height in pixels")
    aspect_ratio: float = Field(description="Width divided by height")
    thumbnail_url: str = Field(description="Short-lived secure signed thumbnail URL")
    created_at: str = Field(description="ISO-8601 UTC timestamp of creation")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "672cf3a9e4b0123456789def",
                "original_filename": "family-portrait.jpg",
                "width_px": 4000,
                "height_px": 3000,
                "aspect_ratio": 1.3333,
                "thumbnail_url": "/api/v1/photos/672cf3a9e4b0123456789def/thumbnail?sig=a1b2c3d4",
                "created_at": "2026-11-07T12:05:00.000Z",
            }
        },
    )


class PhotosListResponse(BaseModel):
    """Collection response containing user photographs and total count."""

    items: list[PhotoSummaryOut] = Field(default_factory=list)
    total: int = Field(description="Total count of active user photographs")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Items per page")
