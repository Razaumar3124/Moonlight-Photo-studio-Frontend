from datetime import UTC, datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.user import PyObjectId


class VisualAnalysis(BaseModel):
    """Zero-AI-token statistical image analysis cached per photograph."""

    dominant_colors: list[str] = Field(default_factory=list)
    color_temperature: str = Field(default="neutral")  # "warm" | "cool" | "neutral"
    brightness: float = Field(default=0.5)
    contrast: float = Field(default=0.5)
    visual_weight: float = Field(default=0.5)
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StoredObjectRef(BaseModel):
    """One stored object (key + size in bytes), kept so storage accounting stays exact."""

    key: str
    size: int = Field(ge=0)


class PhotoInDB(BaseModel):
    """Internal MongoDB document model for photos collection."""

    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: PyObjectId
    original_filename: str
    storage_key: str
    thumbnail_key: str
    preview_key: str
    storage_provider: str = Field(default="cloudflare_r2")
    bucket: str
    mime_type: str
    file_size_bytes: int
    width_px: int
    height_px: int
    aspect_ratio: float
    suggested_orientation: str
    visual_analysis: VisualAnalysis | None = None
    # Sizes of the stored objects (original, preview, thumbnail). Empty on older photos.
    stored_objects: list[StoredObjectRef] = Field(default_factory=list)
    # Objects of a deleted photo that storage failed to remove; the maintenance job retries them.
    purge_pending: list[StoredObjectRef] = Field(default_factory=list)
    status: str = Field(default="ready")
    is_deleted: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def object_refs(self) -> list[StoredObjectRef]:
        """The photo's stored objects with sizes (older photos: only the original is known)."""
        if self.stored_objects:
            return self.stored_objects
        return [
            StoredObjectRef(key=self.storage_key, size=self.file_size_bytes),
            StoredObjectRef(key=self.preview_key, size=0),
            StoredObjectRef(key=self.thumbnail_key, size=0),
        ]

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )
