"""
Pydantic v2 schemas for transaction operations.
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

from app.models.transaction import TransactionStatus, TransactionType


class TransactionBase(BaseModel):
    """Base transaction schema with common fields."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    amount: Decimal = Field(
        ...,
        gt=0,
        description="Transaction amount (must be positive)",
        decimal_places=2,
    )

    currency: StrictStr = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code",
    )

    description: StrictStr | None = Field(
        default=None,
        max_length=500,
        description="Transaction description",
    )

    reference: StrictStr | None = Field(
        default=None,
        max_length=255,
        description="External reference number",
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate currency is uppercase."""
        return v.upper()


class TransactionCreate(TransactionBase):
    """Schema for creating a new transaction."""

    type: TransactionType = Field(
        ...,
        description="Type of transaction",
    )

    destination_account_id: uuid.UUID | None = Field(
        default=None,
        description="Destination account UUID (for transfers)",
    )

    idempotency_key: StrictStr | None = Field(
        default=None,
        max_length=255,
        description="Idempotency key to prevent duplicate transactions",
    )


class TransactionUpdate(BaseModel):
    """Schema for updating transaction status."""

    model_config = ConfigDict(extra="forbid")

    status: TransactionStatus | None = Field(
        default=None,
        description="New transaction status",
    )

    failure_reason: StrictStr | None = Field(
        default=None,
        max_length=1000,
        description="Reason for transaction failure",
    )


class TransactionResponse(TransactionBase):
    """Schema for transaction response."""

    model_config = ConfigDict(from_attributes=True)

    id: PositiveInt
    transaction_id: uuid.UUID
    type: TransactionType
    status: TransactionStatus
    source_account_id: uuid.UUID | None
    destination_account_id: uuid.UUID | None
    idempotency_key: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None


class TransactionListResponse(BaseModel):
    """Paginated list of transactions."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TransactionResponse]
    total: PositiveInt
    page: PositiveInt
    page_size: PositiveInt


class TransactionFilter(BaseModel):
    """Schema for filtering transactions."""

    model_config = ConfigDict(extra="forbid")

    type: TransactionType | None = Field(
        default=None,
        description="Filter by transaction type",
    )

    status: TransactionStatus | None = Field(
        default=None,
        description="Filter by transaction status",
    )

    min_amount: Decimal | None = Field(
        default=None,
        gt=0,
        description="Minimum amount filter",
    )

    max_amount: Decimal | None = Field(
        default=None,
        gt=0,
        description="Maximum amount filter",
    )

    start_date: datetime | None = Field(
        default=None,
        description="Filter transactions from this date",
    )

    end_date: datetime | None = Field(
        default=None,
        description="Filter transactions until this date",
    )
