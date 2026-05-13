"""
Transaction repository for database operations.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Repository for transaction-specific database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Transaction, session)

    async def get_by_transaction_id(
        self,
        transaction_id: uuid.UUID,
    ) -> Transaction | None:
        """Get transaction by external UUID."""
        result = await self.session.execute(
            select(Transaction).where(Transaction.transaction_id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> Transaction | None:
        """Get transaction by idempotency key."""
        result = await self.session.execute(
            select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def get_transactions_by_account(
        self,
        account_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Transaction]:
        """Get all transactions for an account (as source or destination)."""
        result = await self.session.execute(
            select(Transaction)
            .where(
                or_(
                    Transaction.source_account_id == account_id,
                    Transaction.destination_account_id == account_id,
                )
            )
            .offset(skip)
            .limit(limit)
            .order_by(Transaction.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_outgoing_transactions(
        self,
        account_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Transaction]:
        """Get outgoing transactions from an account."""
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.source_account_id == account_id)
            .offset(skip)
            .limit(limit)
            .order_by(Transaction.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_incoming_transactions(
        self,
        account_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Transaction]:
        """Get incoming transactions to an account."""
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.destination_account_id == account_id)
            .offset(skip)
            .limit(limit)
            .order_by(Transaction.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_pending_transactions(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Transaction]:
        """Get all pending transactions."""
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.status == TransactionStatus.PENDING)
            .offset(skip)
            .limit(limit)
            .order_by(Transaction.created_at.asc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        transaction: Transaction,
        status: TransactionStatus,
        failure_reason: str | None = None,
    ) -> Transaction:
        """Update transaction status."""
        transaction.status = status
        if failure_reason is not None:
            transaction.failure_reason = failure_reason
        if status in (TransactionStatus.COMPLETED, TransactionStatus.FAILED):
            transaction.processed_at = datetime.now(datetime.UTC)

        await self.session.flush()
        await self.session.refresh(transaction)
        return transaction

    async def get_transactions_filtered(
        self,
        filters: dict[str, Any] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Transaction]:
        """Get transactions with complex filtering."""
        query: Select = select(Transaction)

        conditions = []

        if filters:
            for key, value in filters.items():
                if value is not None:
                    conditions.append(getattr(Transaction, key) == value)

        if start_date is not None:
            conditions.append(Transaction.created_at >= start_date)

        if end_date is not None:
            conditions.append(Transaction.created_at <= end_date)

        if min_amount is not None:
            conditions.append(Transaction.amount >= min_amount)

        if max_amount is not None:
            conditions.append(Transaction.amount <= max_amount)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.offset(skip).limit(limit).order_by(Transaction.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_total_volume(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        transaction_type: TransactionType | None = None,
    ) -> float:
        """Get total transaction volume for a period."""
        query = select(func.sum(Transaction.amount))

        conditions = [Transaction.status == TransactionStatus.COMPLETED]

        if start_date is not None:
            conditions.append(Transaction.created_at >= start_date)

        if end_date is not None:
            conditions.append(Transaction.created_at <= end_date)

        if transaction_type is not None:
            conditions.append(Transaction.type == transaction_type)

        query = query.where(and_(*conditions))
        result = await self.session.execute(query)
        return float(result.scalar() or 0)


# Import or_ from sqlalchemy
from sqlalchemy import or_  # noqa: E402
