"""
Transaction service layer for business logic.
Handles fund transfers, deposits, withdrawals with proper validation and audit logging.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import structlog

from app.core.exceptions import (
    ConflictError,
    InsufficientFundsError,
    NotFoundError,
)
from app.models.account import Account
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.repositories.account import AccountRepository
from app.repositories.transaction import TransactionRepository

logger = structlog.get_logger(__name__)


class TransactionService:
    """
    Service layer for transaction operations.
    
    Implements business logic for financial transactions including:
    - Fund transfers between accounts
    - Deposits and withdrawals
    - Transaction status management
    - Idempotency handling
    """

    def __init__(
        self,
        transaction_repo: TransactionRepository,
        account_repo: AccountRepository,
    ):
        self.transaction_repo = transaction_repo
        self.account_repo = account_repo

    async def check_idempotency(
        self,
        idempotency_key: str,
    ) -> Transaction | None:
        """
        Check if a transaction with this idempotency key already exists.
        
        Args:
            idempotency_key: Unique idempotency key
            
        Returns:
            Existing transaction if found, None otherwise
        """
        return await self.transaction_repo.get_by_idempotency_key(idempotency_key)

    async def create_transfer(
        self,
        source_account_id: uuid.UUID,
        destination_account_id: uuid.UUID,
        amount: Decimal,
        currency: str | None = None,
        description: str | None = None,
        reference: str | None = None,
        idempotency_key: str | None = None,
    ) -> Transaction:
        """
        Create a fund transfer between two accounts.
        
        Args:
            source_account_id: Source account UUID
            destination_account_id: Destination account UUID
            amount: Transfer amount (must be positive)
            currency: Currency code (optional, defaults to source account currency)
            description: Transfer description
            reference: External reference
            idempotency_key: Idempotency key to prevent duplicates
            
        Returns:
            Created transaction instance
            
        Raises:
            ConflictError: If idempotency key already exists
            NotFoundError: If either account doesn't exist
            InsufficientFundsError: If insufficient balance
            ValueError: If accounts are the same or currency mismatch
        """
        # Check idempotency
        if idempotency_key:
            existing = await self.check_idempotency(idempotency_key)
            if existing:
                logger.info(
                    "Duplicate transaction request detected",
                    idempotency_key=idempotency_key,
                    existing_transaction_id=str(existing.transaction_id),
                )
                raise ConflictError(
                    message="Transaction with this idempotency key already exists",
                    error_code="DUPLICATE_TRANSACTION",
                    details={
                        "transaction_id": str(existing.transaction_id),
                        "status": existing.status.value,
                    },
                )

        # Validate amount
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")

        # Lock and validate source account
        source_account = await self.account_repo.lock_account_for_update(source_account_id)
        if not source_account:
            raise NotFoundError(
                message=f"Source account {source_account_id} not found",
                error_code="SOURCE_ACCOUNT_NOT_FOUND",
            )

        if not source_account.is_active:
            raise ValueError("Source account is not active")

        # Validate destination account
        destination_account = await self.account_repo.get_by_account_id(
            destination_account_id
        )
        if not destination_account:
            raise NotFoundError(
                message=f"Destination account {destination_account_id} not found",
                error_code="DESTINATION_ACCOUNT_NOT_FOUND",
            )

        if not destination_account.is_active:
            raise ValueError("Destination account is not active")

        # Prevent self-transfer
        if source_account_id == destination_account_id:
            raise ValueError("Cannot transfer to the same account")

        # Validate currency
        target_currency = currency.upper() if currency else source_account.currency
        if source_account.currency != target_currency:
            raise ValueError(
                f"Currency mismatch: source account uses {source_account.currency}"
            )
        if destination_account.currency != target_currency:
            raise ValueError(
                f"Currency mismatch: destination account uses {destination_account.currency}"
            )

        # Check sufficient funds
        if source_account.balance < amount:
            raise InsufficientFundsError(
                message=f"Insufficient funds. Available: {source_account.balance}",
                details={
                    "available": str(source_account.balance),
                    "requested": str(amount),
                    "currency": target_currency,
                },
            )

        # Perform atomic transfer
        try:
            # Debit source account
            await self.account_repo.update_balance(
                source_account,
                amount,
                operation="debit",
            )

            # Credit destination account
            await self.account_repo.update_balance(
                destination_account,
                amount,
                operation="credit",
            )

            # Create transaction record
            transaction_data = {
                "type": TransactionType.TRANSFER,
                "amount": amount,
                "currency": target_currency,
                "source_account_id": source_account_id,
                "destination_account_id": destination_account_id,
                "status": TransactionStatus.COMPLETED,
                "description": description,
                "reference": reference,
                "idempotency_key": idempotency_key,
                "processed_at": datetime.now(UTC),
            }

            transaction = await self.transaction_repo.create(transaction_data)

            logger.info(
                "Transfer completed",
                transaction_id=str(transaction.transaction_id),
                source_account_id=str(source_account_id),
                destination_account_id=str(destination_account_id),
                amount=str(amount),
                currency=target_currency,
                source_new_balance=str(source_account.balance),
                dest_new_balance=str(destination_account.balance),
            )

            return transaction

        except Exception as e:
            logger.exception(
                "Transfer failed",
                source_account_id=str(source_account_id),
                destination_account_id=str(destination_account_id),
                amount=str(amount),
                error=str(e),
            )
            raise

    async def create_deposit(
        self,
        account_id: uuid.UUID,
        amount: Decimal,
        currency: str = "USD",
        description: str | None = None,
        reference: str | None = None,
        idempotency_key: str | None = None,
    ) -> Transaction:
        """
        Create a deposit transaction.
        
        Args:
            account_id: Account UUID
            amount: Deposit amount
            currency: Currency code
            description: Transaction description
            reference: External reference
            idempotency_key: Idempotency key
            
        Returns:
            Created transaction instance
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        # Check idempotency
        if idempotency_key:
            existing = await self.check_idempotency(idempotency_key)
            if existing:
                raise ConflictError(
                    message="Transaction with this idempotency key already exists",
                    error_code="DUPLICATE_TRANSACTION",
                )

        account = await self.account_repo.lock_account_for_update(account_id)
        if not account:
            raise NotFoundError(
                message=f"Account {account_id} not found",
                error_code="ACCOUNT_NOT_FOUND",
            )

        if not account.is_active:
            raise ValueError("Account is not active")

        if account.currency != currency.upper():
            raise ValueError(f"Currency mismatch: account uses {account.currency}")

        # Credit account
        await self.account_repo.update_balance(account, amount, operation="credit")

        # Create transaction record
        transaction_data = {
            "type": TransactionType.DEPOSIT,
            "amount": amount,
            "currency": currency.upper(),
            "destination_account_id": account_id,
            "status": TransactionStatus.COMPLETED,
            "description": description,
            "reference": reference,
            "idempotency_key": idempotency_key,
            "processed_at": datetime.now(UTC),
        }

        transaction = await self.transaction_repo.create(transaction_data)

        logger.info(
            "Deposit completed",
            transaction_id=str(transaction.transaction_id),
            account_id=str(account_id),
            amount=str(amount),
            new_balance=str(account.balance),
        )

        return transaction

    async def get_transaction(self, transaction_id: uuid.UUID) -> Transaction:
        """
        Get transaction by UUID.
        
        Args:
            transaction_id: Transaction UUID
            
        Returns:
            Transaction instance
            
        Raises:
            NotFoundError: If transaction doesn't exist
        """
        transaction = await self.transaction_repo.get_by_transaction_id(transaction_id)
        if not transaction:
            raise NotFoundError(
                message=f"Transaction {transaction_id} not found",
                error_code="TRANSACTION_NOT_FOUND",
            )
        return transaction

    async def get_account_transactions(
        self,
        account_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Transaction]:
        """
        Get all transactions for an account.
        
        Args:
            account_id: Account UUID
            skip: Pagination offset
            limit: Maximum results
            
        Returns:
            List of transactions
        """
        return await self.transaction_repo.get_transactions_by_account(
            account_id,
            skip=skip,
            limit=limit,
        )

    async def cancel_pending_transaction(
        self,
        transaction_id: uuid.UUID,
    ) -> Transaction:
        """
        Cancel a pending transaction.
        
        Args:
            transaction_id: Transaction UUID
            
        Returns:
            Updated transaction instance
            
        Raises:
            NotFoundError: If transaction doesn't exist
            ValueError: If transaction is not in PENDING status
        """
        transaction = await self.transaction_repo.get_by_transaction_id(transaction_id)
        if not transaction:
            raise NotFoundError(
                message=f"Transaction {transaction_id} not found",
                error_code="TRANSACTION_NOT_FOUND",
            )

        if transaction.status != TransactionStatus.PENDING:
            raise ValueError(
                f"Cannot cancel transaction in {transaction.status.value} status"
            )

        updated = await self.transaction_repo.update_status(
            transaction,
            TransactionStatus.CANCELLED,
        )

        logger.info(
            "Transaction cancelled",
            transaction_id=str(transaction_id),
            previous_status=TransactionStatus.PENDING.value,
        )

        return updated
