"""Signed downloads for the development storage backend (``STORAGE_BACKEND=local``).

Plays the role of Cloudflare R2 presigned URLs: ``LocalStorage.generate_presigned_url``
produces ``/api/v1/storage/local/{key}?exp=…&sig=…``. Requests without a valid,
unexpired signature, or made while R2 is active, get the same 404.
"""

from fastapi import APIRouter, Query, Response

from app.api.dependencies import StorageDep
from app.core.exceptions import ResourceNotFoundException
from app.storage.local_storage import LocalStorage

router = APIRouter(prefix="/storage", tags=["Storage (development)"])


@router.get("/local/{key:path}", include_in_schema=False)
async def get_local_object(
    key: str,
    storage: StorageDep,
    exp: int = Query(..., description="Expiry, epoch seconds"),
    sig: str = Query(..., min_length=64, max_length=64, description="HMAC-SHA256 signature"),
) -> Response:
    if not isinstance(storage, LocalStorage) or not storage.verify_signature(key, exp, sig):
        raise ResourceNotFoundException(
            message="Requested media was not found in storage.", field="key"
        )

    data, content_type = await storage.get_object(key)
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )
