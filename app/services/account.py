from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.account import AccountRepository
from ..models.account import Account, User
from ..schemas.account import AccountCreate, AccountResponse, UpdateAccount
from ..core.exceptions import raise_not_found, raise_forbidden
import logging

logger = logging.getLogger(__name__)

class AccountService:
    def __init__(self, account_repo: AccountRepository):
        self.account_repo = account_repo

    async def create_account(self, account_data: AccountCreate) -> AccountResponse:
        # Check if account number already exists
        existing_account = await self.account_repo.get_by_account_number(account_data.account_number)
        if existing_account:
            raise_forbidden("Account number already exists")
        
        # Create the account
        account_dict = account_data.model_dump()
        account = await self.account_repo.create(account_dict)
        return AccountResponse.model_validate(account)

    async def get_account(self, account_id: int) -> AccountResponse:
        account = await self.account_repo.get(account_id)
        if not account:
            raise raise_not_found("Account not found")
        return AccountResponse.model_validate(account)

    async def get_account_by_user(self, user_id: int) -> list[AccountResponse]:
        accounts = await self.account_repo.get_by_user_id(user_id)
        return [AccountResponse.model_validate(account) for account in accounts]

    async def update_account(self, account_id: int, update_data: UpdateAccount) -> AccountResponse:
        account = await self.account_repo.get(account_id)
        if not account:
            raise raise_not_found("Account not found")

        # Update only the fields that are provided
        update_dict = update_data.model_dump(exclude_unset=True)
        if not update_dict:
            return AccountResponse.model_validate(account)

        updated_account = await self.account_repo.update(account_id, update_dict)
        if not updated_account:
            raise raise_not_found("Account not found after update")
        return AccountResponse.model_validate(updated_account)

    async def deposit(self, account_id: int, amount: float, idempotency_key: str) -> AccountResponse:
        # Note: Idempotency is handled by middleware, but we can add a check here if needed.
        account = await self.account_repo.get(account_id)
        if not account:
            raise raise_not_found("Account not found")
        if not account.is_active:
            raise raise_forbidden("Account is inactive")

        # Update balance
        account.balance += amount
        await self.account_repo.update(account_id, {"balance": account.balance})
        return AccountResponse.model_validate(account)

    async def withdraw(self, account_id: int, amount: float, idempotency_key: str) -> AccountResponse:
        account = await self.account_repo.get(account_id)
        if not account:
            raise raise_not_found("Account not found")
        if not account.is_active:
            raise raise_forbidden("Account is inactive")
        if account.balance < amount:
            raise raise_forbidden("Insufficient funds")

        # Update balance
        account.balance -= amount
        await self.account_repo.update(account_id, {"balance": account.balance})
        return AccountResponse.model_validate(account)

    async def deactivate_account(self, account_id: int) -> dict:
        account = await self.account_repo.get(account_id)
        if not account:
            raise raise_not_found("Account not found")
        if not account.is_active:
            # Already inactive, but we can still return success or a specific message.
            return {"message": "Account is already inactive"}
        
        await self.account_repo.update(account_id, {"is_active": False})
        return {"message": "Account deactivated successfully"}