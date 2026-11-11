from fastapi import APIRouter, Query, status

from app.api.dependencies import TemplateServiceDep
from app.schemas.common import ApiErrorResponse
from app.schemas.template import TemplatesListResponse

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get(
    "",
    response_model=TemplatesListResponse,
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
    summary="List layout templates",
    description=(
        "Retrieves curated gallery wall layout templates with slot positions, "
        "relative wall ratios, and recommended wall dimensions."
    ),
)
async def list_templates(
    template_service: TemplateServiceDep,
    category: str | None = Query(
        default=None,
        description="Filter by layout category (e.g. grid, salon, centre, row, triptych)",
        examples=["grid"],
    ),
    min_frames: int | None = Query(
        default=None,
        description="Minimum frame slot count",
        ge=1,
        examples=[3],
    ),
    max_frames: int | None = Query(
        default=None,
        description="Maximum frame slot count",
        ge=1,
        examples=[9],
    ),
) -> TemplatesListResponse:
    """EP-TMPL-01: List layout templates."""
    return await template_service.get_templates(
        category=category,
        min_frames=min_frames,
        max_frames=max_frames,
    )
