"""
Common Pydantic schemas for API responses.
"""

import uuid
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Standardized error response schema."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    trace_id: str = Field(
        ...,
        description="Unique trace ID for debugging",
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details",
    )


class SuccessResponse(BaseModel, Generic[T]):
    """Generic success response wrapper."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(default=True)
    data: T | None = Field(default=None)
    message: str | None = Field(default=None)


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    model_config = ConfigDict(extra="forbid")

    items: list[T]
    total: PositiveInt
    page: PositiveInt
    page_size: PositiveInt
    has_more: bool = Field(
        default=False,
        description="Whether there are more items available",
    )


class HealthCheckResponse(BaseModel):
    """Health check response schema."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="Service version")
    timestamp: float = Field(..., description="Unix timestamp of check")


class TokenResponse(BaseModel):
    """JWT token response schema."""

    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds",
    )


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., description="JWT refresh token")


class LoginRequest(BaseModel):
    """Login request schema."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class AuditLogEntry(BaseModel):
    """Audit log entry schema for compliance."""

    model_config = ConfigDict(from_attributes=True)

    id: PositiveInt
    event_type: str
    user_id: str | None
    resource_type: str
    resource_id: str | uuid.UUID | None
    action: str
    timestamp: float
    ip_address: str | None
    user_agent: str | None
    metadata: dict[str, Any] | None = None
