"""Filesystem object storage for local development (``STORAGE_BACKEND=local``).

Mirrors the ``R2Storage`` interface so services don't know which backend is active.

Security:
* Keys are validated (``[A-Za-z0-9._-]`` segments, no ``.``/``..``, no absolute or
  backslash paths) and the resolved path must stay inside the storage root.
* Writes are atomic (temp file + ``os.replace``), so readers never see partial files.
* Files are never exposed as a static directory. Downloads go through
  ``GET /api/v1/storage/local/{key}`` with an HMAC signature and expiry, like an R2
  presigned URL.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundException, StorageUnavailableException

logger = logging.getLogger("moonlight_studio.local_storage")

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_META_SUFFIX = ".meta.json"
_MAX_KEY_LENGTH = 512


class InvalidStorageKeyError(ValueError):
    """Raised for object keys that could escape the storage root or collide with metadata."""


def _sign(key: str, expires_at: int) -> str:
    secret = get_settings().SECRET_KEY.encode("utf-8")
    message = f"local-storage:{key}:{expires_at}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


class LocalStorage:
    """Development object storage rooted at a single directory."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def bucket_name(self) -> str:
        return "local"

    # ------------------------------------------------------------------ paths

    def _path_for(self, key: str) -> Path:
        if not key or len(key) > _MAX_KEY_LENGTH or key.endswith(_META_SUFFIX):
            raise InvalidStorageKeyError("Invalid storage key")
        segments = key.split("/")
        for segment in segments:
            if segment in ("", ".", "..") or not _SEGMENT_RE.match(segment):
                raise InvalidStorageKeyError("Invalid storage key")
        path = self._root.joinpath(*segments).resolve()
        if not path.is_relative_to(self._root):
            raise InvalidStorageKeyError("Invalid storage key")
        return path

    @staticmethod
    def _meta_path(path: Path) -> Path:
        return path.with_name(path.name + _META_SUFFIX)

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------- interface

    async def ping(self) -> float:
        """Check that the root is writable; returns latency in milliseconds."""
        start = time.perf_counter()

        def _probe() -> None:
            self._root.mkdir(parents=True, exist_ok=True)
            fd, probe = tempfile.mkstemp(dir=self._root, prefix=".ping-")
            os.close(fd)
            Path(probe).unlink()

        try:
            await asyncio.to_thread(_probe)
        except OSError as exc:
            logger.error("Local storage root is not writable: %s", exc)
            raise StorageUnavailableException(issue="Local storage folder is not writable") from exc
        return round((time.perf_counter() - start) * 1000, 2)

    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        path = self._path_for(key)
        meta = json.dumps({"content_type": content_type, "metadata": metadata or {}}).encode()

        def _write() -> None:
            self._atomic_write(path, data)
            self._atomic_write(self._meta_path(path), meta)

        try:
            await asyncio.to_thread(_write)
        except OSError as exc:
            logger.error("Local storage write failed for key %s: %s", key, exc)
            raise StorageUnavailableException(issue="Failed to write object to storage") from exc
        logger.debug("Stored local object %s (%d bytes)", key, len(data))
        return key

    async def get_object(self, key: str) -> tuple[bytes, str]:
        try:
            path = self._path_for(key)
        except InvalidStorageKeyError as exc:
            raise ResourceNotFoundException(
                message="Requested media was not found in storage.", field="key"
            ) from exc

        def _read() -> tuple[bytes, str]:
            data = path.read_bytes()
            content_type = "application/octet-stream"
            try:
                meta = json.loads(self._meta_path(path).read_text(encoding="utf-8"))
                content_type = str(meta.get("content_type") or content_type)
            except (OSError, ValueError):
                pass
            return data, content_type

        try:
            return await asyncio.to_thread(_read)
        except FileNotFoundError as exc:
            raise ResourceNotFoundException(
                message="Requested media was not found in storage.", field="key"
            ) from exc
        except OSError as exc:
            logger.error("Local storage read failed for key %s: %s", key, exc)
            raise StorageUnavailableException(issue="Failed to read object from storage") from exc

    async def delete_object(self, key: str) -> bool:
        try:
            path = self._path_for(key)
        except InvalidStorageKeyError:
            return False

        def _delete() -> bool:
            existed = path.is_file()
            path.unlink(missing_ok=True)
            self._meta_path(path).unlink(missing_ok=True)
            return existed

        try:
            return await asyncio.to_thread(_delete)
        except OSError as exc:
            logger.warning("Local storage delete failed for key %s: %s", key, exc)
            return False

    async def delete_objects(self, keys: list[str]) -> None:
        for key in keys:
            await self.delete_object(key)

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Signed, expiring API URL (relative to the API host), like an R2 presigned URL."""
        self._path_for(key)
        settings = get_settings()
        lifetime = min(max(expires_in, 60), settings.LOCAL_STORAGE_URL_EXPIRATION_SECONDS)
        expires_at = int(datetime.now(UTC).timestamp()) + lifetime
        signature = _sign(key, expires_at)
        return (
            f"{settings.API_V1_STR}/storage/local/{quote(key, safe='/')}"
            f"?exp={expires_at}&sig={signature}"
        )

    def verify_signature(self, key: str, expires_at: int, signature: str) -> bool:
        """Constant-time check of a URL produced by :meth:`generate_presigned_url`."""
        if expires_at < int(datetime.now(UTC).timestamp()):
            return False
        try:
            self._path_for(key)
        except InvalidStorageKeyError:
            return False
        return hmac.compare_digest(_sign(key, expires_at), signature)
