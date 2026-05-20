from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from .base import BaseRepository
from ..models.transaction import Transaction, TransactionType
from typing import Optional, List

class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id: int) -> Optional[Transaction]:
        result = await self.session.execute(select(Transaction).where(Transaction.id == id))
        return result.scalars().first()

    async def get_multi(self, *, skip: int = 0, limit: int = 100) -> List[Transaction]:
        result = await self.session.execute(select(Transaction).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, obj_in: dict) -> Transaction:
        db_obj = Transaction(**obj_in)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(self, id: int, obj_in: dict) -> Optional[Transaction]:
        db_obj = await self.get(id)
        if db_obj:
            for field, value in obj_in.items():
                setattr(db_obj, field, value)
            await self.session.commit()
            await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: int) -> bool:
        db_obj = await self.get(id)
        if db_obj:
            await self.session.delete(db_obj)
            await self.session.commit()
            return True
        return False

    # Additional methods specific to transactions
    async def get_by_account_id(self, account_id: int, *, skip: int = 0, limit: int = 100) -> List[Transaction]:
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()