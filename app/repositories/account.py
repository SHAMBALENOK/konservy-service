"""
Account repository for database operations.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account]):
    """Repository for account-specific database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Account, session)

    async def get_by_account_id(self, account_id: uuid.UUID) -> Account | None:
        """Get account by external UUID."""
        result = await self.session.execute(
            select(Account).where(Account.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> Account | None:
        """Get account by user ID."""
        result = await self.session.execute(
            select(Account).where(Account.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_account_number(self, account_number: str) -> Account | None:
        """Get account by account number."""
        result = await self.session.execute(
            select(Account).where(Account.account_number == account_number)
        )
        return result.scalar_one_or_none()

    async def update_balance(
        self,
        account: Account,
        amount: Decimal,
        operation: str = "credit",
    ) -> Account:
        """
        Update account balance atomically.
        
        Args:
            account: The account to update
            amount: Amount to add or subtract
            operation: 'credit' to add, 'debit' to subtract
            
        Returns:
            Updated account instance
            
        Raises:
            ValueError: If operation would result in negative balance
        """
        if operation == "credit":
            account.balance += amount
        elif operation == "debit":
            new_balance = account.balance - amount
            if new_balance < 0:
                raise ValueError("Insufficient funds")
            account.balance = new_balance
        else:
            raise ValueError(f"Invalid operation: {operation}")

        await self.session.flush()
        await self.session.refresh(account)
        return account

    async def get_active_accounts(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Account]:
        """Get all active accounts with pagination."""
        result = await self.session.execute(
            select(Account)
            .where(Account.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(Account.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_accounts_by_currency(
        self,
        currency: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Account]:
        """Get accounts filtered by currency."""
        result = await self.session.execute(
            select(Account)
            .where(Account.currency == currency.upper())
            .where(Account.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(Account.created_at.desc())
        )
        return list(result.scalars().all())

    async def lock_account_for_update(
        self,
        account_id: uuid.UUID,
    ) -> Account | None:
        """
        Lock account row for update (SELECT FOR UPDATE).
        Used for atomic balance operations.
        """
        result = await self.session.execute(
            select(Account)
            .where(Account.account_id == account_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()
