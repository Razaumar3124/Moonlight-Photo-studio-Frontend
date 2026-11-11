from fastapi import APIRouter, Query, status

from app.api.dependencies import CatalogServiceDep
from app.schemas.catalog import FramesListResponse
from app.schemas.common import ApiErrorResponse

router = APIRouter(prefix="/frames", tags=["Catalog"])


@router.get(
    "",
    response_model=FramesListResponse,
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
    summary="List frame molding profiles",
    description=(
        "Retrieves commercial frame molding profiles with face dimensions, "
        "available finish colors with hex codes, and linear pricing."
    ),
)
async def list_frames(
    catalog_service: CatalogServiceDep,
    material_id: str | None = Query(
        default=None,
        description="Filter by parent frame material ObjectId (24-hex string)",
        examples=["672520012e5c6a1b2c3d4e01"],
    ),
    color: str | None = Query(
        default=None,
        description="Filter by color finish name substring (case-insensitive)",
        examples=["Oak"],
    ),
    min_width: float | None = Query(
        default=None,
        description="Minimum face profile width in inches",
        ge=0,
        examples=[0.75],
    ),
    max_width: float | None = Query(
        default=None,
        description="Maximum face profile width in inches",
        ge=0,
        examples=[1.5],
    ),
) -> FramesListResponse:
    """EP-CAT-02: List frame moldings catalog."""
    return await catalog_service.get_frames(
        material_id=material_id,
        color=color,
        min_width=min_width,
        max_width=max_width,
    )
