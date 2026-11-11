from fastapi import APIRouter, Query, status

from app.api.dependencies import CatalogServiceDep
from app.schemas.catalog import FrameMaterialsListResponse
from app.schemas.common import ApiErrorResponse

router = APIRouter(prefix="/frame-materials", tags=["Catalog"])


@router.get(
    "",
    response_model=FrameMaterialsListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ApiErrorResponse,
            "description": "Validation failed on query parameters",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ApiErrorResponse,
            "description": "Database is unreachable",
        },
    },
    summary="List available frame materials",
    description=(
        "Retrieves master list of frame materials (wood, metal, synthetic) "
        "with optional category and inventory availability filtering."
    ),
)
async def list_frame_materials(
    catalog_service: CatalogServiceDep,
    category: str | None = Query(
        default=None,
        description="Optional material category: 'wood', 'metal', 'synthetic'",
        examples=["wood"],
    ),
    available_only: bool = Query(
        default=True,
        description="Filter only available items (default: true)",
    ),
) -> FrameMaterialsListResponse:
    """EP-CAT-01: List frame materials catalog."""
    return await catalog_service.get_frame_materials(
        category=category,
        available_only=available_only,
    )
