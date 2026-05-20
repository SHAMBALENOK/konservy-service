from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.transaction import TransactionService
from ..schemas.transaction import TransferRequest, DepositRequest, TransactionDetail
from ..core.exceptions import raise_not_found, raise_forbidden
from ..repositories.account import AccountRepository
from ..core.security import decode_token
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Dependency to get the database session (will be overridden in main.py)
async def get_db():
    raise NotImplementedError("Database session not configured")

# Dependency to get the account repository
async def get_account_repo(db: AsyncSession = Depends(get_db)):
    return AccountRepository(db)

# Dependency to get the transaction service
async def get_transaction_service(
    account_repo: AccountRepository = Depends(get_account_repo)
):
    # We need to get the transaction repository as well, but for simplicity,
    # we'll create it inside the service or pass the session directly.
    # Let's adjust: we'll pass the session to the service and let it create its own repositories.
    from ..repositories.transaction import TransactionRepository
    return TransactionService(
        transaction_repo=TransactionRepository(None),  # We'll fix this in the dependency
        account_repo=account_repo
    )

# Better approach: create a dependency that provides the session and then create services with it
async def get_transaction_service_with_session(db: AsyncSession = Depends(get_db)):
    from ..repositories.transaction import TransactionRepository
    from ..repositories.account import AccountRepository
    transaction_repo = TransactionRepository(db)
    account_repo = AccountRepository(db)
    return TransactionService(
        transaction_repo=transaction_repo,
        account_repo=account_repo
    )

# Dependency to get the current user from token (simplified)
async def get_current_user(token: str = Header(None)) -> int:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Remove 'Bearer ' prefix if present
    if token.startswith("Bearer "):
        token = token[7:]
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return int(user_id)

@router.post("/transfer", response_model=dict)
async def transfer_funds(
    transfer_request: TransferRequest,
    transaction_service: TransactionService = Depends(get_transaction_service_with_session),
    current_user: int = Depends(get_current_user),
    idempotency_key: str = Header(...)
):
    # For transfer, the source user is the current_user (from query parameter in docs, but we'll use header for simplicity
    # or we can get it from the authenticated user as per the docs: "current_user" - Source user ID (for transfers)
    # We'll get it from the authenticated user for security.
    source_user_id = current_user
    
    try:
        result = await transaction_service.transfer(
            source_user_id=source_user_id,
            transfer_request=transfer_request,
            idempotency_key=idempotency_key
        )
        return result
    except Exception as e:
        if "insufficient funds" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        elif "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

@router.post("/deposit", response_model=dict)
async def deposit_funds(
    deposit_request: DepositRequest,
    transaction_service: TransactionService = Depends(get_transaction_service_with_session),
    current_user: int = Depends(get_current_user),
    idempotency_key: str = Header(...)
):
    # Check that the account belongs to the current user
    account_repo = transaction_service.account_repo  # Access the account repo from the service
    account = await account_repo.get(deposit_request.account_id)
    if not account:
        raise raise_not_found("Account not found")
    if account.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to deposit to this account"
        )
    
    try:
        result = await transaction_service.deposit(
            deposit_request=deposit_request,
            idempotency_key=idempotency_key
        )
        return result
    except Exception as e:
        if "insufficient funds" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

@router.get("/", response_model=list[TransactionDetail])
async def list_transactions(
    transaction_service: TransactionService = Depends(get_transaction_service_with_session),
    current_user: int = Depends(get_current_user)
):
    # Get all accounts for the user and then get transactions for each account
    # For simplicity, we'll just return an empty list or we can implement fetching all transactions for the user
    # We'll need to get the user's accounts first
    accounts = await transaction_service.account_repo.get_by_user_id(current_user)
    if not accounts:
        return []
    
    # Get transactions for the first account (or we could merge all accounts)
    # For simplicity, we'll return transactions for the first account
    account_id = accounts[0].id
    transactions = await transaction_service.get_account_transactions(account_id)
    return transactions

@router.get("/{transaction_id}", response_model=TransactionDetail)
async def get_transaction_detail(
    transaction_id: int,
    transaction_service: TransactionService = Depends(get_transaction_service_with_session),
    current_user: int = Depends(get_current_user)
):
    transaction = await transaction_service.transaction_repo.get(transaction_id)
    if not transaction:
        raise raise_not_found("Transaction not found")
    
    # Check if the transaction belongs to the current user (via the account)
    account = await transaction_service.account_repo.get(transaction.account_id)
    if not account or account.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this transaction"
        )
    
    return transaction

@router.get("/account/{account_id}", response_model=list[TransactionDetail])
async def get_account_transactions(
    account_id: int,
    transaction_service: TransactionService = Depends(get_transaction_service_with_session),
    current_user: int = Depends(get_current_user)
):
    # Check if the account belongs to the current user
    account = await transaction_service.account_repo.get(account_id)
    if not account:
        raise raise_not_found("Account not found")
    if account.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access transactions for this account"
        )
    
    transactions = await transaction_service.get_account_transactions(account_id)
    return transactions