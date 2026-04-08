"""
Transaction model for banking operations.
All monetary amounts use Decimal for precision.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TransactionType(str, Enum):
    """Transaction type enumeration."""

    TRANSFER = "transfer"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    REFUND = "refund"


class TransactionStatus(str, Enum):
    """Transaction status enumeration."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Transaction(Base):
    """
    Financial transaction model.
    
    Tracks all money movements between accounts or external sources.
    Amount is always stored as Decimal with proper precision.
    """

    __tablename__ = "transactions"

    # Internal primary key
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External-facing UUID (used in API)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        index=True,
        nullable=False,
    )

    # Idempotency key for preventing duplicate transactions
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )

    # Transaction details
    type: Mapped[TransactionType] = mapped_column(
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )

    # Account relationships
    source_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.account_id"),
        index=True,
        nullable=True,
    )

    destination_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.account_id"),
        index=True,
        nullable=True,
    )

    # Status tracking
    status: Mapped[TransactionStatus] = mapped_column(
        default=TransactionStatus.PENDING,
        nullable=False,
    )

    # Metadata
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Error handling
    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    # Relationships
    source_account: Mapped["Account | None"] = relationship(
        "Account",
        foreign_keys=[source_account_id],
        back_populates="transactions_outgoing",
    )

    destination_account: Mapped["Account | None"] = relationship(
        "Account",
        foreign_keys=[destination_account_id],
        back_populates="transactions_incoming",
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(transaction_id={self.transaction_id}, "
            f"amount={self.amount}, status={self.status})>"
        )
