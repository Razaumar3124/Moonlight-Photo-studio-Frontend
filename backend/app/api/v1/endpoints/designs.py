from typing import Literal

from fastapi import APIRouter, Path, Query, Response, status

from app.api.dependencies import CurrentUserDep, DesignServiceDep
from app.schemas.common import ApiErrorResponse
from app.schemas.design import (
    CreateDesignRequest,
    DesignDetailOut,
    DesignListResponse,
    DesignOut,
    DesignVersionSummaryResponse,
    SaveDesignVersionRequest,
    UpdateDesignRequest,
)

router = APIRouter(prefix="/designs", tags=["Designs & Versions Management"])


@router.post(
    "",
    response_model=DesignOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorResponse, "description": "Unauthenticated"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ApiErrorResponse,
            "description": "Validation error",
        },
    },
    summary="Create a new design draft",
    description="EP-DSGN-01: Creates a new gallery wall project owned by the authenticated user.",
)
async def create_design(
    req: CreateDesignRequest,
    current_user: CurrentUserDep,
    design_service: DesignServiceDep,
) -> DesignOut:
    """EP-DSGN-01: Save a new gallery wall design."""
    return await design_service.create_design(user_id=str(current_user.id), req=req)


@router.get(
    "",
    response_model=DesignListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorResponse, "description": "Unauthenticated"},
    },
    summary="List the authenticated user's designs",
    description="EP-DSGN-04: Returns paginated list of active gallery walls owned by the user.",
)
async def list_designs(
    current_user: CurrentUserDep,
    design_service: DesignServiceDep,
    page: int = Query(default=1, ge=1, description="Page number starting at 1"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status_filter: Literal["draft", "saved", "ordered"] | None = Query(
        default=None,
        alias="status",
        description="Filter by design workflow status",
    ),
    search: str | None = Query(
        default=None,
        max_length=80,
        description="Search substring in design title",
    ),
    sort: str = Query(
        default="updated_at:desc",
        description="Sort field and direction (e.g. updated_at:desc, created_at:desc, title:asc)",
    ),
) -> DesignListResponse:
    """EP-DSGN-04: List the current user's designs."""
    return await design_service.list_designs(
        user_id=str(current_user.id),
        page=page,
        page_size=page_size,
        status=status_filter,
        search=search,
        sort=sort,
    )


@router.get(
    "/{id}",
    response_model=DesignDetailOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorResponse, "description": "Unauthenticated"},
        status.HTTP_403_FORBIDDEN: {
            "model": ApiErrorResponse,
            "description": "Access denied (IDOR protection)",
        },
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse, "description": "Design not found"},
    },
    summary="Retrieve a saved design",
    description=(
        "EP-DSGN-03: Returns full design details and current layout snapshot "
        "for canvas restoration."
    ),
)
async def get_design(
    current_user: CurrentUserDep,
    design_service: DesignServiceDep,
    id: str = Path(..., description="24-character hexadecimal MongoDB ObjectId of the design"),
) -> DesignDetailOut:
    """EP-DSGN-03: Retrieve a saved design by ID."""
    return await design_service.get_design(design_id=id, user_id=str(current_user.id))


@router.patch(
    "/{id}",
    response_model=DesignOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorResponse, "description": "Unauthenticated"},
        status.HTTP_403_FORBIDDEN: {
            "model": ApiErrorResponse,
            "description": "Access denied (IDOR protection)",
        },
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse, "description": "Design not found"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ApiErrorResponse,
            "description": "Validation error",
        },
    },
    summary="Update an existing design",
    description="EP-DSGN-05: Modifies design title, description, wall settings, or status.",
)
async def update_design(
    req: UpdateDesignRequest,
    current_user: CurrentUserDep,
    design_service: DesignServiceDep,
    id: str = Path(..., description="24-character hexadecimal MongoDB ObjectId of the design"),
) -> DesignOut:
    """EP-DSGN-05: Update an existing design."""
    return await design_service.update_design(design_id=id, user_id=str(current_user.id), req=req)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Design successfully deleted"},
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorResponse, "description": "Unauthenticated"},
        status.HTTP_403_FORBIDDEN: {
            "model": ApiErrorResponse,
            "description": "Access denied (IDOR protection)",
        },
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse, "description": "Design not found"},
    },
    summary="Delete a saved design",
    description="EP-DSGN-06: Soft-deletes a gallery wall design. Associated photos are preserved.",
)
async def delete_design(
    current_user: CurrentUserDep,
    design_service: DesignServiceDep,
    id: str = Path(..., description="24-character hexadecimal MongoDB ObjectId of the design"),
) -> Response:
    """EP-DSGN-06: Delete a saved design."""
    await design_service.delete_design(design_id=id, user_id=str(current_user.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{id}/versions",
    response_model=DesignVersionSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorResponse, "description": "Unauthenticated"},
        status.HTTP_403_FORBIDDEN: {
            "model": ApiErrorResponse,
            "description": "Access denied or unowned photo reference",
        },
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse, "description": "Design not found"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ApiErrorResponse,
            "description": "Validation error or geometry violation",
        },
    },
    summary="Create an immutable design version",
    description="EP-DSGN-02: Saves an immutable layout snapshot with atomic sequential versioning.",
)
async def create_design_version(
    req: SaveDesignVersionRequest,
    current_user: CurrentUserDep,
    design_service: DesignServiceDep,
    id: str = Path(..., description="24-character hexadecimal MongoDB ObjectId of the design"),
) -> DesignVersionSummaryResponse:
    """EP-DSGN-02: Create an immutable design version."""
    return await design_service.create_version(
        design_id=id,
        user_id=str(current_user.id),
        req=req,
    )
