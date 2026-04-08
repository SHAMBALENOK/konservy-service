"""
Pydantic v2 schemas for account operations.
Uses strict validation and Decimal for monetary amounts.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    StrictStr,
    field_validator,
)
from pydantic.types import StringConstraints


class AccountBase(BaseModel):
    """Base account schema with common fields."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        populate_by_name=True,
    )

    currency: StrictStr = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code",
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate currency is uppercase and valid format."""
        return v.upper()


class AccountCreate(AccountBase):
    """Schema for creating a new account."""

    user_id: StrictStr = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique user identifier",
    )

    initial_balance: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Initial deposit amount (must be non-negative)",
    )


class AccountUpdate(BaseModel):
    """Schema for updating account properties."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = Field(
        default=None,
        description="Account active status",
    )


class AccountResponse(AccountBase):
    """Schema for account response."""

    model_config = ConfigDict(from_attributes=True)

    id: PositiveInt
    account_id: uuid.UUID
    user_id: StrictStr
    account_number: StrictStr
    balance: Decimal = Field(
        ...,
        description="Current account balance",
        decimal_places=2,
    )
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AccountListResponse(BaseModel):
    """Paginated list of accounts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[AccountResponse]
    total: PositiveInt
    page: PositiveInt
    page_size: PositiveInt


class BalanceAdjustment(BaseModel):
    """Schema for balance adjustment (deposit/withdrawal)."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(
        ...,
        gt=0,
        description="Amount to adjust (must be positive)",
        decimal_places=2,
    )

    description: StrictStr | None = Field(
        default=None,
        max_length=500,
        description="Optional description for the adjustment",
    )

    reference: StrictStr | None = Field(
        default=None,
        max_length=255,
        description="Optional external reference",
    )


class TransferRequest(BaseModel):
    """Schema for transferring funds between accounts."""

    model_config = ConfigDict(extra="forbid")

    destination_account_id: uuid.UUID = Field(
        ...,
        description="Destination account UUID",
    )

    amount: Decimal = Field(
        ...,
        gt=0,
        description="Transfer amount (must be positive)",
        decimal_places=2,
    )

    currency: StrictStr | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Currency (defaults to source account currency)",
    )

    description: StrictStr | None = Field(
        default=None,
        max_length=500,
        description="Transfer description",
    )

    reference: StrictStr | None = Field(
        default=None,
        max_length=255,
        description="External reference number",
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        """Validate currency is uppercase if provided."""
        if v is not None:
            return v.upper()
        return v
