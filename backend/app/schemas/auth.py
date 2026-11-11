import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.security import normalize_email, normalize_phone
from app.schemas.user import UserOut

# Regex validation rules matching frontend specifications
_NAME_RE = re.compile(
    r"^[A-Za-z\u00C0-\u024F\u0900-\u0D7F][A-Za-z\u00C0-\u024F\u0900-\u0D7F\s.'’–\-]*$"
)
_PASSWORD_HAS_LETTER = re.compile(r"[A-Za-z]")
_PASSWORD_HAS_DIGIT = re.compile(r"\d")


class AuthTokens(BaseModel):
    """Token pair response schema."""

    access_token: str = Field(..., description="Short-lived Bearer JWT access token")
    refresh_token: str = Field(..., description="Cryptographically secure refresh token")
    token_type: Literal["bearer"] = Field(default="bearer", description="Token type")
    expires_in: int = Field(
        ..., description="Access token expiration lifetime in seconds", examples=[1800]
    )

    model_config = ConfigDict(extra="forbid")


class AuthResponse(BaseModel):
    """Authentication success envelope for registration and login."""

    user: UserOut
    tokens: AuthTokens

    model_config = ConfigDict(extra="forbid")


class RegisterRequest(BaseModel):
    """User registration payload."""

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Full customer name",
        examples=["Aarav Sharma"],
    )
    email: EmailStr = Field(
        ..., description="Unique email address", examples=["customer@example.com"]
    )
    phone: str = Field(
        ...,
        description="Indian mobile number (10 digits or E.164 +91...)",
        examples=["+919876543210"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Account password (min 8 chars, 1 letter, 1 digit)",
        examples=["SecurePassword123!"],
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_fields(self) -> "RegisterRequest":
        # Normalize and validate full name
        cleaned_name = " ".join(self.full_name.strip().split())
        if len(cleaned_name) < 2:
            raise ValueError("Full name must be at least 2 characters")
        if not _NAME_RE.match(cleaned_name):
            raise ValueError(
                "Use letters only for name. Spaces, hyphens, and apostrophes are fine."
            )
        self.full_name = cleaned_name

        # Normalize email
        self.email = normalize_email(self.email)

        # Normalize and validate phone
        normalized_phone = normalize_phone(self.phone)
        if (
            not normalized_phone
            or not normalized_phone.startswith("+91")
            or len(normalized_phone) != 13
        ):
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        self.phone = normalized_phone

        # Validate password complexity
        if not _PASSWORD_HAS_LETTER.search(self.password) or not _PASSWORD_HAS_DIGIT.search(
            self.password
        ):
            raise ValueError(
                "Password must be at least 8 characters and include both a letter and a number."
            )

        return self


class LoginRequest(BaseModel):
    """Login payload supporting email, phone, or single identifier."""

    email: EmailStr | None = Field(default=None, description="Registered email address")
    phone: str | None = Field(default=None, description="Registered Indian mobile number")
    identifier: str | None = Field(default=None, description="Combined mobile or email field")
    password: str = Field(..., min_length=1, max_length=128, description="Account password")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_identifier(self) -> "LoginRequest":
        raw_id = self.identifier or self.email or self.phone
        if not raw_id:
            raise ValueError("Provide either an email address or mobile number.")

        raw_str = str(raw_id).strip()
        if "@" in raw_str:
            self.email = normalize_email(raw_str)
            self.phone = None
        else:
            norm_phone = normalize_phone(raw_str)
            if not norm_phone:
                raise ValueError("Enter a valid email or 10-digit mobile number.")
            self.phone = norm_phone
            self.email = None

        return self


class RefreshTokenRequest(BaseModel):
    """Optional payload for token refresh (if not using httpOnly cookie)."""

    refresh_token: str | None = Field(
        default=None, description="Refresh token string if not using cookies"
    )

    model_config = ConfigDict(extra="forbid")


class ForgotPasswordRequest(BaseModel):
    """Password recovery initiation payload."""

    email: EmailStr = Field(..., description="Registered account email address")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def normalize(self) -> "ForgotPasswordRequest":
        self.email = normalize_email(self.email)
        return self


class ForgotPasswordResponse(BaseModel):
    """Non-enumerating response for password recovery initiation."""

    message: str = Field(
        default="If an account is associated with this email, a verification code was sent.",
        description="Status message",
    )
    cooldown_seconds: int = Field(
        default=60,
        description="Minimum seconds to wait before requesting another OTP",
    )

    model_config = ConfigDict(extra="forbid")


class VerifyOtpRequest(BaseModel):
    """OTP code verification payload."""

    email: EmailStr = Field(..., description="Account email address")
    otp: str = Field(
        ..., min_length=6, max_length=6, description="6-digit numeric verification code"
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_and_normalize(self) -> "VerifyOtpRequest":
        self.email = normalize_email(self.email)
        cleaned_otp = self.otp.strip()
        if not cleaned_otp.isdigit() or len(cleaned_otp) != 6:
            raise ValueError("Verification code must be exactly 6 digits.")
        self.otp = cleaned_otp
        return self


class VerifyOtpResponse(BaseModel):
    """Successful OTP verification payload containing temporary reset authorization token."""

    reset_token: str = Field(..., description="Single-use password reset authorization token")
    expires_in_seconds: int = Field(
        default=600,
        description="Validity lifetime in seconds for the reset token",
    )

    model_config = ConfigDict(extra="forbid")


class ResetPasswordRequest(BaseModel):
    """Payload to finalize password reset using verified reset token."""

    reset_token: str = Field(..., min_length=10, description="Reset token from OTP verification")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (min 8 chars, 1 letter, 1 digit)",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_password_policy(self) -> "ResetPasswordRequest":
        if not _PASSWORD_HAS_LETTER.search(self.new_password) or not _PASSWORD_HAS_DIGIT.search(
            self.new_password
        ):
            raise ValueError(
                "Password must be at least 8 characters and include both a letter and a number."
            )
        return self


class ResetPasswordResponse(BaseModel):
    """Response returned upon successful password update."""

    message: str = Field(
        default="Your password has been successfully reset. Please sign in with your new password.",
        description="Confirmation message",
    )

    model_config = ConfigDict(extra="forbid")


class GoogleAuthRequest(BaseModel):
    """Payload containing Google OAuth 2.0 ID Token."""

    id_token: str = Field(
        ..., min_length=10, description="Google issued OpenID Connect JWT ID token"
    )

    model_config = ConfigDict(extra="forbid")
