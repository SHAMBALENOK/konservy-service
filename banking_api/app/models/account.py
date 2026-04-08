"""
Account model for banking operations.
Uses UUID for external-facing IDs, integer for internal PK.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Account(Base):
    """
    Bank account model.
    
    All monetary amounts use Decimal for precision.
    External account_id is UUID for security (not sequential).
    """

    __tablename__ = "accounts"

    # Internal primary key
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # External-facing UUID (used in API)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        index=True,
        nullable=False,
    )

    # Owner reference (user_id from auth system)
    user_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    # Account details
    account_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )

    balance: Mapped[Decimal] = mapped_column(
        nullable=False,
        default=Decimal("0.00"),
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    transactions_outgoing: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="Transaction.source_account_id",
        back_populates="source_account",
    )

    transactions_incoming: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="Transaction.destination_account_id",
        back_populates="destination_account",
    )

    def __repr__(self) -> str:
        return f"<Account(account_id={self.account_id}, balance={self.balance})>"
