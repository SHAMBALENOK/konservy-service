from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.transaction import TransactionRepository
from ..repositories.account import AccountRepository
from ..models.transaction import Transaction, TransactionType
from ..schemas.transaction import TransferRequest, DepositRequest
from ..core.exceptions import raise_not_found, raise_forbidden
import logging

logger = logging.getLogger(__name__)

class TransactionService:
    def __init__(self, transaction_repo: TransactionRepository, account_repo: AccountRepository):
        self.transaction_repo = transaction_repo
        self.account_repo = account_repo

    async def transfer(self, source_user_id: int, transfer_request: TransferRequest, idempotency_key: str) -> dict:
        """
        Transfer funds from source user's account to destination account.
        Note: The endpoint expects a query parameter `current_user` (source user ID) and a body with destination_account_id and amount.
        We assume the source user has exactly one account for simplicity, or we take the first active account.
        In a real system, we might let the user specify which account to debit.
        """
        # Get the source account for the user (assuming one account per user for simplicity)
        source_accounts = await self.account_repo.get_by_user_id(source_user_id)
        if not source_accounts:
            raise raise_not_found("Source account not found for the user")
        # We'll use the first active account; in a real system, we might have an account selection mechanism.
        source_account = next((acc for acc in source_accounts if acc.is_active), None)
        if not source_account:
            raise raise_forbidden("No active account found for the user")

        # Check if the destination account exists and is active
        destination_account = await self.account_repo.get(transfer_request.destination_account_id)
        if not destination_account:
            raise raise_not_found("Destination account not found")
        if not destination_account.is_active:
            raise raise_forbidden("Destination account is inactive")

        # Check sufficient funds in source account
        if source_account.balance < transfer_request.amount:
            raise raise_forbidden("Insufficient funds")

        # Perform the transfer (in a real system, this should be a single transaction)
        # Deduct from source
        source_account.balance -= transfer_request.amount
        # Add to destination
        destination_account.balance += transfer_request.amount

        # Update accounts
        await self.account_repo.update(source_account.id, {"balance": source_account.balance})
        await self.account_repo.update(destination_account.id, {"balance": destination_account.balance})

        # Create transaction records for both accounts? Or one transaction record that represents the transfer?
        # According to the model, we have a transaction per account. We can create two transaction records:
        #   One for the source (withdrawal) and one for the destination (deposit).
        # But the endpoint is called "transfer" and we might want to link them. We'll use the transaction_type_details to link.

        # We'll create one transaction record for the source account (with type transfer and details pointing to destination)
        # and another for the destination account (with type transfer and details pointing to source) OR
        # we can create one transaction record and duplicate it? Let's follow the model: each transaction belongs to one account.

        # For the source account: transaction_type = TRANSFER, amount = -transfer_request.amount? 
        # But our model doesn't support negative amounts. Instead, we can record the absolute amount and use the type to indicate direction? 
        # Alternatively, we can have two transactions: one withdrawal and one deposit, and link them via transaction_type_details.

        # Let's do two transactions:
        #   Source: transaction_type = WITHDRAWAL, amount = transfer_request.amount, details: { "transfer_to": destination_account.id }
        #   Destination: transaction_type = DEPOSIT, amount = transfer_request.amount, details: { "transfer_from": source_account.id }

        # However, the documentation says the transaction endpoint has a transfer endpoint that moves funds between accounts.
        # We'll follow the requirement: the transfer endpoint should create a transaction record that represents the transfer.

        # Looking at the Transaction model, it has an account_id (the account the transaction is associated with) and a transaction_type.
        # For a transfer, we might want to record two transactions (one out, one in) but the endpoint is singular.
        # Alternatively, we can record one transaction on the source account with type TRANSFER and negative amount? But we don't allow negative.

        # Let's change the model? But we cannot change the model because it's already defined and we are following the documentation.

        # Re-examining the documentation for the transaction endpoint:
        #   POST /api/v1/transactions/transfer              # Transfer funds between accounts
        #   and the query parameter: current_user (source user ID)
        #   The body of the transfer request is not specified in the documentation, but we have defined TransferRequest with destination_account_id and amount.

        # We have to decide how to record the transfer in the transaction table.

        # Option 1: Record two transactions (one for each account) and return both? But the endpoint is expected to return one transaction? 
        #   The response for the transfer endpoint is not specified in the documentation. We can return a summary.

        # Option 2: Record one transaction that represents the transfer, but then we have to decide which account it belongs to.

        # Given the ambiguity, we will record two transactions: one for the source (withdrawal) and one for the destination (deposit), and we will link them by a common transfer ID in the transaction_type_details.

        # However, the Transaction model does not have a transfer_id field. We have transaction_type_details (JSON) which we can use to store a transfer group ID.

        # Let's generate a transfer group ID (could be a UUID) and store it in both transactions' transaction_type_details.

        import uuid
        transfer_group_id = str(uuid.uuid4())

        # Source transaction (withdrawal)
        source_transaction_data = {
            "account_id": source_account.id,
            "transaction_type": TransactionType.WITHDRAWAL.value,
            "amount": transfer_request.amount,
            "description": f"Transfer to account {destination_account.account_number}",
            "transaction_type_details": {
                "transfer_group_id": transfer_group_id,
                "counterparty_account_id": destination_account.id,
                "direction": "out"
            }
        }
        source_transaction = await self.transaction_repo.create(source_transaction_data)

        # Destination transaction (deposit)
        destination_transaction_data = {
            "account_id": destination_account.id,
            "transaction_type": TransactionType.DEPOSIT.value,
            "amount": transfer_request.amount,
            "description": f"Transfer from account {source_account.account_number}",
            "transaction_type_details": {
                "transfer_group_id": transfer_group_id,
                "counterparty_account_id": source_account.id,
                "direction": "in"
            }
        }
        destination_transaction = await self.transaction_repo.create(destination_transaction_data)

        # Return a response that indicates the transfer was successful and includes the transaction IDs or a transfer ID.
        return {
            "message": "Transfer successful",
            "transfer_id": transfer_group_id,
            "source_transaction_id": source_transaction.id,
            "destination_transaction_id": destination_transaction.id
        }

    async def deposit(self, deposit_request: DepositRequest, idempotency_key: str) -> dict:
        account = await self.account_repo.get(deposit_request.account_id)
        if not account:
            raise raise_not_found("Account not found")
        if not account.is_active:
            raise raise_forbidden("Account is inactive")

        # Update balance
        account.balance += deposit_request.amount
        await self.account_repo.update(account.id, {"balance": account.balance})

        # Create transaction record
        transaction_data = {
            "account_id": account.id,
            "transaction_type": TransactionType.DEPOSIT.value,
            "amount": deposit_request.amount,
            "description": deposit_request.description or "Deposit",
            "transaction_type_details": None
        }
        transaction = await self.transaction_repo.create(transaction_data)

        return {
            "message": "Deposit successful",
            "transaction_id": transaction.id
        }

    async def get_account_transactions(self, account_id: int, skip: int = 0, limit: int = 100) -> list:
        account = await self.account_repo.get(account_id)
        if not account:
            raise raise_not_found("Account not found")
        transactions = await self.transaction_repo.get_by_account_id(account_id, skip=skip, limit=limit)
        return transactions