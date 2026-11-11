from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiErrorDetail(BaseModel):
    """Granular error detail pointing to a specific request field or condition."""

    field: str = Field(
        default="",
        description="Request field or resource attribute the issue relates to",
        examples=["database", "email", "width_inches"],
    )
    issue: str = Field(
        ...,
        description="Human-readable description of the constraint violation",
        examples=["Field is required", "Database connection failed"],
    )

    model_config = ConfigDict(extra="forbid")


class ApiErrorPayload(BaseModel):
    """Core error payload matching the standard API contract envelope."""

    code: str = Field(
        ...,
        description="Machine-readable uppercase error identifier",
        examples=["DATABASE_UNAVAILABLE", "VALIDATION_ERROR", "RESOURCE_NOT_FOUND"],
    )
    message: str = Field(
        ...,
        description="Client-safe summary description of the failure",
        examples=["Database service is currently unreachable", "Invalid request parameters"],
    )
    details: list[ApiErrorDetail] = Field(
        default_factory=list,
        description="List of specific field violations or context details",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO-8601 UTC timestamp of the error event",
        examples=["2026-11-07T12:00:00.000Z"],
    )

    model_config = ConfigDict(extra="forbid")


class ApiErrorResponse(BaseModel):
    """Top-level standard error envelope returned for all 4xx and 5xx responses."""

    error: ApiErrorPayload

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database service is currently unreachable",
                    "details": [
                        {
                            "field": "database",
                            "issue": "MongoDB ping timed out or connection failed",
                        }
                    ],
                    "timestamp": "2026-11-07T12:00:00.000Z",
                }
            }
        },
    )
