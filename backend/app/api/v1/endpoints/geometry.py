"""Phase 5 Geometry & Intelligent Wall Layout API Endpoints.

Implements EP-GEO-01 (validate-layout), EP-GEO-02 (generate-layout),
regenerate-layout, and redesign-layout with optional authentication.
"""

from fastapi import APIRouter, Request, status

from app.api.dependencies import (
    LayoutServiceDep,
    OptionalCurrentUserDep,
    RedesignServiceDep,
)
from app.schemas.geometry import (
    GenerateLayoutRequest,
    GenerateLayoutResponse,
    RedesignLayoutRequest,
    RedesignLayoutResponse,
    RegenerateLayoutRequest,
    RegenerateLayoutResponse,
    ValidateLayoutRequest,
    ValidateLayoutResponse,
)

router = APIRouter(prefix="/geometry", tags=["Geometry & Layout Engine"])


@router.post(
    "/validate-layout",
    response_model=ValidateLayoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate layout bounds and collisions (EP-GEO-01)",
    description=(
        "Authoritative 2D boundary and collision validation for user-placed frames. "
        "Returns HTTP 200 with is_valid=false and collision details when frames overlap."
    ),
)
async def validate_layout(
    req: ValidateLayoutRequest,
    layout_service: LayoutServiceDep,
) -> ValidateLayoutResponse:
    """EP-GEO-01: Validate wall layout bounds, collisions, and clearances."""
    return layout_service.validate_layout(req)


@router.post(
    "/generate-layout",
    response_model=GenerateLayoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate gallery wall layout (EP-GEO-02)",
    description=(
        "Generate collision-free gallery wall arrangement using hybrid architecture: "
        "Groq LLM creative recommendations (<200 tokens) with deterministic Python geometry solver."
    ),
)
async def generate_layout(
    req: GenerateLayoutRequest,
    http_request: Request,
    layout_service: LayoutServiceDep,
    current_user: OptionalCurrentUserDep,
) -> GenerateLayoutResponse:
    """EP-GEO-02: Generate optimal gallery wall arrangement."""
    client_ip = http_request.client.host if http_request.client else "anonymous"
    caller_id = str(current_user.id) if current_user else client_ip
    user_id = str(current_user.id) if current_user else None

    return await layout_service.generate_layout(
        req=req,
        caller_id=caller_id,
        current_user_id=user_id,
    )


@router.post(
    "/regenerate",
    response_model=RegenerateLayoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Regenerate layout with new variation seed",
    description=(
        "Explore alternative valid arrangements while preserving layout style. "
        "Uses pure Python geometry — 0 AI tokens guaranteed."
    ),
)
async def regenerate_layout(
    req: RegenerateLayoutRequest,
    layout_service: LayoutServiceDep,
    current_user: OptionalCurrentUserDep,
) -> RegenerateLayoutResponse:
    """Regenerate layout exploring alternative valid arrangements with next seed."""
    user_id = str(current_user.id) if current_user else None
    return await layout_service.regenerate_layout(
        req=req,
        current_user_id=user_id,
    )


@router.post(
    "/redesign",
    response_model=RedesignLayoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Redesign layout with new compositional archetype",
    description=(
        "Produce a meaningfully different composition (e.g. grid -> salon -> centre -> row) "
        "or creative direction from Groq, resolved deterministically by Python geometry."
    ),
)
async def redesign_layout(
    req: RedesignLayoutRequest,
    http_request: Request,
    redesign_service: RedesignServiceDep,
    current_user: OptionalCurrentUserDep,
) -> RedesignLayoutResponse:
    """Redesign layout with new compositional archetype."""
    client_ip = http_request.client.host if http_request.client else "anonymous"
    caller_id = str(current_user.id) if current_user else client_ip
    user_id = str(current_user.id) if current_user else None

    return await redesign_service.redesign_layout(
        req=req,
        caller_id=caller_id,
        current_user_id=user_id,
    )
