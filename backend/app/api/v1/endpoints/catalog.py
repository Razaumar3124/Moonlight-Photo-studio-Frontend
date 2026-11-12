"""Planner catalog: frame sizes, finishes, mount colours, paint shades, layouts and rules."""

from fastapi import APIRouter, Response, status

from app.schemas.catalog import PlannerCatalogResponse
from app.services.catalog_service import build_planner_catalog

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get(
    "",
    response_model=PlannerCatalogResponse,
    status_code=status.HTTP_200_OK,
    summary="Memory Wall planner catalog",
    description=(
        "Every option the planner offers, with the stable IDs that designs and quotes store, "
        "and the physical rules (in inches) the server validates against. Public and static."
    ),
)
async def get_planner_catalog(response: Response) -> PlannerCatalogResponse:
    response.headers["Cache-Control"] = "public, max-age=300"
    return build_planner_catalog()
