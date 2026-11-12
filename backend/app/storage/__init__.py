"""Object storage for photos and quote previews.

Two interchangeable backends implement :class:`ObjectStorage`:

* ``R2Storage``    – Cloudflare R2 (S3-compatible). Required in production.
* ``LocalStorage`` – files under ``LOCAL_STORAGE_PATH`` for development.

``STORAGE_BACKEND`` selects one; :func:`create_storage` builds it.
"""

from typing import Protocol, runtime_checkable

from app.core.config import Settings, get_settings


@runtime_checkable
class ObjectStorage(Protocol):
    """Async object-storage interface shared by every backend."""

    @property
    def bucket_name(self) -> str: ...

    async def ping(self) -> float: ...

    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str: ...

    async def get_object(self, key: str) -> tuple[bytes, str]: ...

    async def delete_object(self, key: str) -> bool: ...

    async def delete_objects(self, keys: list[str]) -> None: ...

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str: ...


def create_storage(settings: Settings | None = None) -> ObjectStorage:
    """Instantiate the storage backend selected by ``STORAGE_BACKEND``."""
    cfg = settings or get_settings()
    if cfg.STORAGE_BACKEND == "local":
        from app.storage.local_storage import LocalStorage

        return LocalStorage(root=cfg.local_storage_root)

    from app.storage.r2_storage import R2Storage

    return R2Storage()
