from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    """Public user profile response schema matching frontend contract."""

    id: str = Field(
        ..., description="Unique 24-character hex user ID", examples=["672cf1a9e4b0123456789abc"]
    )
    email: str = Field(
        ..., description="User's primary email address", examples=["customer@example.com"]
    )
    full_name: str = Field(..., description="User's full display name", examples=["Aarav Sharma"])
    phone: str | None = Field(
        default=None, description="E.164 formatted mobile number", examples=["+919876543210"]
    )
    role: str = Field(
        default="customer", description="User authorization role", examples=["customer"]
    )
    is_active: bool = Field(default=True, description="Account active status")
    created_at: str = Field(..., description="Account creation UTC ISO timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "672cf1a9e4b0123456789abc",
                "email": "customer@example.com",
                "full_name": "Aarav Sharma",
                "phone": "+919876543210",
                "role": "customer",
                "is_active": True,
                "created_at": "2026-11-07T12:00:00.000Z",
            }
        },
    )
