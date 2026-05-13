"""
Account service layer for business logic.
Handles account operations with proper validation and audit logging.
"""

import uuid
from decimal import Decimal

import structlog

from app.core.exceptions import (
    ConflictError,
    InsufficientFundsError,
    NotFoundError,
)
from app.models.account import Account
from app.repositories.account import AccountRepository

logger = structlog.get_logger(__name__)


class AccountService:
    """
    Service layer for account operations.
    
    Implements business logic for account management including:
    - Account creation with validation
    - Balance operations (deposit/withdrawal)
    - Account status management
    """

    def __init__(self, account_repo: AccountRepository):
        self.account_repo = account_repo

    async def create_account(
        self,
        user_id: str,
        currency: str = "USD",
        initial_balance: Decimal = Decimal("0.00"),
    ) -> Account:
        """
        Create a new bank account for a user.
        
        Args:
            user_id: Unique user identifier
            currency: ISO 4217 currency code
            initial_balance: Starting balance (must be non-negative)
            
        Returns:
            Created account instance
            
        Raises:
            ConflictError: If user already has an account
        """
        # Check if user already has an account
        existing = await self.account_repo.get_by_user_id(user_id)
        if existing:
            raise ConflictError(
                message=f"User {user_id} already has an account",
                error_code="USER_ALREADY_HAS_ACCOUNT",
            )

        # Generate account number (format: ACC + 10 random digits)
        account_number = f"ACC{uuid.uuid4().hex[:10].upper()}"

        # Validate initial balance
        if initial_balance < 0:
            raise ValueError("Initial balance cannot be negative")

        account_data = {
            "user_id": user_id,
            "account_number": account_number,
            "currency": currency.upper(),
            "balance": initial_balance,
            "is_active": True,
        }

        account = await self.account_repo.create(account_data)

        logger.info(
            "Account created",
            account_id=str(account.account_id),
            user_id=user_id,
            account_number=account_number,
            currency=currency,
            initial_balance=str(initial_balance),
        )

        return account

    async def get_account(self, account_id: uuid.UUID) -> Account:
        """
        Get account by UUID.
        
        Args:
            account_id: Account UUID
            
        Returns:
            Account instance
            
        Raises:
            NotFoundError: If account doesn't exist
        """
        account = await self.account_repo.get_by_account_id(account_id)
        if not account:
            raise NotFoundError(
                message=f"Account {account_id} not found",
                error_code="ACCOUNT_NOT_FOUND",
            )
        return account

    async def get_account_by_user(self, user_id: str) -> Account:
        """
        Get account by user ID.
        
        Args:
            user_id: User identifier
            
        Returns:
            Account instance
            
        Raises:
            NotFoundError: If account doesn't exist
        """
        account = await self.account_repo.get_by_user_id(user_id)
        if not account:
            raise NotFoundError(
                message=f"No account found for user {user_id}",
                error_code="ACCOUNT_NOT_FOUND",
            )
        return account

    async def deposit(
        self,
        account_id: uuid.UUID,
        amount: Decimal,
        description: str | None = None,
        reference: str | None = None,
    ) -> Account:
        """
        Deposit funds into an account.
        
        Args:
            account_id: Account UUID
            amount: Amount to deposit (must be positive)
            description: Optional description
            reference: Optional external reference
            
        Returns:
            Updated account instance
            
        Raises:
            NotFoundError: If account doesn't exist
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        # Lock account for update
        account = await self.account_repo.lock_account_for_update(account_id)
        if not account:
            raise NotFoundError(
                message=f"Account {account_id} not found",
                error_code="ACCOUNT_NOT_FOUND",
            )

        if not account.is_active:
            raise ValueError("Cannot deposit to inactive account")

        updated_account = await self.account_repo.update_balance(
            account,
            amount,
            operation="credit",
        )

        logger.info(
            "Deposit processed",
            account_id=str(account_id),
            amount=str(amount),
            currency=account.currency,
            new_balance=str(updated_account.balance),
            description=description,
            reference=reference,
        )

        return updated_account

    async def withdraw(
        self,
        account_id: uuid.UUID,
        amount: Decimal,
        description: str | None = None,
        reference: str | None = None,
    ) -> Account:
        """
        Withdraw funds from an account.
        
        Args:
            account_id: Account UUID
            amount: Amount to withdraw (must be positive)
            description: Optional description
            reference: Optional external reference
            
        Returns:
            Updated account instance
            
        Raises:
            NotFoundError: If account doesn't exist
            InsufficientFundsError: If insufficient balance
            ValueError: If amount is not positive or account inactive
        """
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")

        # Lock account for update
        account = await self.account_repo.lock_account_for_update(account_id)
        if not account:
            raise NotFoundError(
                message=f"Account {account_id} not found",
                error_code="ACCOUNT_NOT_FOUND",
            )

        if not account.is_active:
            raise ValueError("Cannot withdraw from inactive account")

        try:
            updated_account = await self.account_repo.update_balance(
                account,
                amount,
                operation="debit",
            )
        except ValueError as e:
            if "Insufficient funds" in str(e):
                raise InsufficientFundsError(
                    message=f"Insufficient funds. Available: {account.balance}",
                    details={"available": str(account.balance), "requested": str(amount)},
                )
            raise

        logger.info(
            "Withdrawal processed",
            account_id=str(account_id),
            amount=str(amount),
            currency=account.currency,
            new_balance=str(updated_account.balance),
            description=description,
            reference=reference,
        )

        return updated_account

    async def deactivate_account(self, account_id: uuid.UUID) -> Account:
        """
        Deactivate an account.
        
        Args:
            account_id: Account UUID
            
        Returns:
            Updated account instance
            
        Raises:
            NotFoundError: If account doesn't exist
            ValueError: If account has non-zero balance
        """
        account = await self.account_repo.get_by_account_id(account_id)
        if not account:
            raise NotFoundError(
                message=f"Account {account_id} not found",
                error_code="ACCOUNT_NOT_FOUND",
            )

        # Prevent deactivation with non-zero balance
        if account.balance != 0:
            raise ValueError(
                f"Cannot deactivate account with non-zero balance: {account.balance}"
            )

        updated_account = await self.account_repo.update(
            account,
            {"is_active": False},
        )

        logger.warning(
            "Account deactivated",
            account_id=str(account_id),
            user_id=account.user_id,
        )

        return updated_account

    async def activate_account(self, account_id: uuid.UUID) -> Account:
        """
        Activate a previously deactivated account.
        
        Args:
            account_id: Account UUID
            
        Returns:
            Updated account instance
            
        Raises:
            NotFoundError: If account doesn't exist
        """
        account = await self.account_repo.get_by_account_id(account_id)
        if not account:
            raise NotFoundError(
                message=f"Account {account_id} not found",
                error_code="ACCOUNT_NOT_FOUND",
            )

        updated_account = await self.account_repo.update(
            account,
            {"is_active": True},
        )

        logger.info(
            "Account activated",
            account_id=str(account_id),
            user_id=account.user_id,
        )

        return updated_account
