import asyncio
import logging
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundException, StorageUnavailableException
from app.storage.types import StoredObject

logger = logging.getLogger("moonlight_studio.r2_storage")


class R2Storage:
    """Thread-safe S3-compatible storage client for Cloudflare R2."""

    def __init__(self, s3_client: Any = None, bucket_name: str | None = None) -> None:
        self._client = s3_client
        self._bucket = bucket_name

    def _get_client(self) -> Any:
        if self._client is None:
            settings = get_settings()
            config = Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=15,
            )
            self._client = boto3.client(
                service_name="s3",
                endpoint_url=settings.r2_effective_endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID or "mock-access-key",
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY or "mock-secret-key",
                region_name="auto",
                config=config,
            )
        return self._client

    @property
    def bucket_name(self) -> str:
        if self._bucket:
            return self._bucket
        return get_settings().R2_BUCKET_NAME

    async def ping(self) -> float:
        """Ping Cloudflare R2 bucket and measure round-trip latency in milliseconds."""
        import time

        client = self._get_client()
        bucket = self.bucket_name
        start = time.perf_counter()

        def _sync_ping() -> None:
            client.head_bucket(Bucket=bucket)

        try:
            await asyncio.to_thread(_sync_ping)
            latency_ms = (time.perf_counter() - start) * 1000
            return round(latency_ms, 2)
        except ClientError as exc:
            logger.error("R2 ping failed for bucket %s: %s", bucket, exc)
            raise StorageUnavailableException(
                issue=f"Cloudflare R2 bucket '{bucket}' unreachable or permission denied: {exc}"
            ) from exc
        except Exception as exc:
            logger.error("Unexpected error during R2 ping: %s", exc)
            raise StorageUnavailableException(issue=str(exc)) from exc

    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload raw binary data to Cloudflare R2 asynchronously."""
        client = self._get_client()
        bucket = self.bucket_name
        req_meta = metadata or {}

        def _sync_put() -> dict[str, Any]:
            return client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata=req_meta,
            )

        try:
            await asyncio.to_thread(_sync_put)
            logger.debug("Uploaded object to R2: %s (%d bytes)", key, len(data))
            return key
        except ClientError as exc:
            logger.error("R2 put_object failed for key %s: %s", key, exc)
            raise StorageUnavailableException(
                issue=f"Failed to upload object {key} to Cloudflare R2: {exc}"
            ) from exc
        except Exception as exc:
            logger.error("Unexpected error during R2 put_object: %s", exc)
            raise StorageUnavailableException(issue=str(exc)) from exc

    async def get_object(self, key: str) -> tuple[bytes, str]:
        """Download raw binary object from Cloudflare R2 asynchronously."""
        client = self._get_client()
        bucket = self.bucket_name

        def _sync_get() -> tuple[bytes, str]:
            resp = client.get_object(Bucket=bucket, Key=key)
            body = resp["Body"].read()
            c_type = resp.get("ContentType", "application/octet-stream")
            return body, c_type

        try:
            return await asyncio.to_thread(_sync_get)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "NotFound"):
                raise ResourceNotFoundException(
                    message=f"Photo media for key '{key}' not found in storage.",
                    field="key",
                ) from exc
            logger.error("R2 get_object error for key %s: %s", key, exc)
            raise StorageUnavailableException(issue=str(exc)) from exc
        except ResourceNotFoundException:
            raise
        except Exception as exc:
            logger.error("Unexpected error during R2 get_object: %s", exc)
            raise StorageUnavailableException(issue=str(exc)) from exc

    async def delete_object(self, key: str) -> bool:
        """Delete an object from Cloudflare R2 asynchronously."""
        client = self._get_client()
        bucket = self.bucket_name

        def _sync_delete() -> None:
            client.delete_object(Bucket=bucket, Key=key)

        try:
            await asyncio.to_thread(_sync_delete)
            logger.debug("Deleted object from R2: %s", key)
            return True
        except ClientError as exc:
            logger.warning("R2 delete_object warning for key %s: %s", key, exc)
            return False
        except Exception as exc:
            logger.warning("Unexpected error during R2 delete_object for key %s: %s", key, exc)
            return False

    async def delete_objects(self, keys: list[str]) -> list[str]:
        """Bulk delete; returns the keys that are gone afterwards (absent counts as gone)."""
        if not keys:
            return []
        client = self._get_client()
        bucket = self.bucket_name

        def _sync_bulk_delete() -> list[str]:
            payload = {"Objects": [{"Key": k} for k in keys], "Quiet": True}
            resp = client.delete_objects(Bucket=bucket, Delete=payload)
            failed = {e.get("Key") for e in (resp or {}).get("Errors", []) or []}
            return [k for k in keys if k not in failed]

        try:
            gone = await asyncio.to_thread(_sync_bulk_delete)
            logger.debug("Bulk deleted %d objects from R2", len(gone))
            return gone
        except Exception as exc:
            logger.warning("Failed to bulk delete R2 objects: %s", exc)
            # Fall back to individual deletes
            return [k for k in keys if await self.delete_object(k)]

    async def list_objects(self, prefix: str = "") -> list[StoredObject]:
        """List every object under ``prefix`` (paginated ListObjectsV2, 1000 keys per call)."""
        client = self._get_client()
        bucket = self.bucket_name

        def _sync_list() -> list[StoredObject]:
            found: list[StoredObject] = []
            token: str | None = None
            while True:
                kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
                if token:
                    kwargs["ContinuationToken"] = token
                resp = client.list_objects_v2(**kwargs)
                for item in resp.get("Contents", []) or []:
                    found.append(StoredObject(item["Key"], int(item["Size"]), item["LastModified"]))
                if not resp.get("IsTruncated"):
                    return found
                token = resp.get("NextContinuationToken")

        try:
            return await asyncio.to_thread(_sync_list)
        except Exception as exc:
            logger.error("R2 list_objects failed: %s", exc)
            raise StorageUnavailableException(issue=str(exc)) from exc

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate short-lived presigned GET URL for an R2 object."""
        client = self._get_client()
        bucket = self.bucket_name

        def _sync_presign() -> str:
            return client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )

        try:
            return await asyncio.to_thread(_sync_presign)
        except Exception as exc:
            logger.error("Failed to generate presigned URL for %s: %s", key, exc)
            raise StorageUnavailableException(issue=str(exc)) from exc
