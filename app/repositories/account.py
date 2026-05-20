from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from .base import BaseRepository
from ..models.account import Account, User
from typing import Optional, List

class AccountRepository(BaseRepository[Account]):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id: int) -> Optional[Account]:
        result = await self.session.execute(select(Account).where(Account.id == id))
        return result.scalars().first()

    async def get_multi(self, *, skip: int = 0, limit: int = 100) -> List[Account]:
        result = await self.session.execute(select(Account).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, obj_in: dict) -> Account:
        db_obj = Account(**obj_in)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(self, id: int, obj_in: dict) -> Optional[Account]:
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

    # Additional methods specific to accounts
    async def get_by_user_id(self, user_id: int) -> List[Account]:
        result = await self.session.execute(select(Account).where(Account.user_id == user_id))
        return result.scalars().all()

    async def get_by_account_number(self, account_number: str) -> Optional[Account]:
        result = await self.session.execute(select(Account).where(Account.account_number == account_number))
        return result.scalars().first()