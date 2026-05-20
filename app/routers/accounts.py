from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.account import AccountService
from ..schemas.account import AccountCreate, AccountResponse, UpdateAccount
from ..core.exceptions import raise_not_found, raise_forbidden
from ..repositories.account import AccountRepository
from ..core.security import decode_token
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["Accounts"])

# Dependency to get the database session (will be overridden in main.py)
async def get_db():
    raise NotImplementedError("Database session not configured")

# Dependency to get the account repository
async def get_account_repo(db: AsyncSession = Depends(get_db)):
    return AccountRepository(db)

# Dependency to get the account service
async def get_account_service(
    account_repo: AccountRepository = Depends(get_account_repo)
):
    return AccountService(account_repo=account_repo)

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

@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account_data: AccountCreate,
    account_service: AccountService = Depends(get_account_service),
    current_user: int = Depends(get_current_user)
):
    # Ensure the authenticated user is creating their own account (or has permission)
    # For simplicity, we'll allow users to create accounts only for themselves
    if account_data.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create account for another user"
        )
    
    try:
        account = await account_service.create_account(account_data)
        return account
    except Exception as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account"
        )

@router.get("/", response_model=list[AccountResponse])
async def list_accounts(
    account_service: AccountService = Depends(get_account_service),
    current_user: int = Depends(get_current_user)
):
    accounts = await account_service.get_account_by_user(current_user)
    return accounts

@router.get("/{account_id}", response_model=AccountResponse)
async def get_account_detail(
    account_id: int,
    account_service: AccountService = Depends(get_account_service),
    current_user: int = Depends(get_current_user)
):
    # Get the account to check ownership
    account = await account_service.get_account(account_id)
    if not account:
        raise raise_not_found("Account not found")
    
    # Check if the account belongs to the current user
    if account.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this account"
        )
    
    return account

@router.get("/user/{user_id}", response_model=list[AccountResponse])
async def get_account_by_user_id(
    user_id: int,
    account_service: AccountService = Depends(get_account_service),
    current_user: int = Depends(get_current_user)
):
    # Users can only get their own accounts
    if user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access accounts for another user"
        )
    
    accounts = await account_service.get_account_by_user(user_id)
    return accounts

@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    update_data: UpdateAccount,
    account_service: AccountService = Depends(get_account_service),
    current_user: int = Depends(get_current_user)
):
    # Get the account to check ownership
    account = await account_service.get_account(account_id)
    if not account:
        raise raise_not_found("Account not found")
    
    # Check if the account belongs to the current user
    if account.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this account"
        )
    
    try:
        updated_account = await account_service.update_account(account_id, update_data)
        return updated_account
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{account_id}/deposit", response_model=AccountResponse)
async def deposit_funds(
    account_id: int,
    amount: float,
    account_service: AccountService = Depends(get_account_service),
    current_user: int = Depends(get_current_user),
    idempotency_key: str = Header(...)
):
    # Get the account to check ownership
    account = await account_service.get_account(account_id)
    if not account:
        raise raise_not_found("Account not found")
    
    # Check if the account belongs to the current user
    if account.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to deposit to this account"
        )
    
    # Validate amount
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deposit amount must be greater than zero"
        )
    
    try:
        updated_account = await account_service.deposit(account_id, amount, idempotency_key)
        return updated_account
    except Exception as e:
        if "insufficient funds" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{account_id}/withdraw", response_model=AccountResponse)
async def withdraw_funds(
    account_id: int,
    amount: float,
    account_service: AccountService = Depends(get_account_service),
    current_user: int = Depends(get_current_user),
    idempotency_key: str = Header(...)
):
    # Get the account to check ownership
    account = await account_service.get_account(account_id)
    if not account:
        raise raise_not_found("Account not found")
    
    # Check if the account belongs to the current user
    if account.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to withdraw from this account"
        )
    
    # Validate amount
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Withdrawal amount must be greater than zero"
        )
    
    try:
        updated_account = await account_service.withdraw(account_id, amount, idempotency_key)
        return updated_account
    except Exception as e:
        if "insufficient funds" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_account(
    account_id: int,
    account_service: AccountService = Depends(get_account_service),
    current_user: int = Depends(get_current_user)
):
    # Get the account to check ownership
    account = await account_service.get_account(account_id)
    if not account:
        raise raise_not_found("Account not found")
    
    # Check if the account belongs to the current user
    if account.user_id != current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to deactivate this account"
        )
    
    result = await account_service.deactivate_account(account_id)
    if "message" in result:
        # For 204 No Content, we don't return a body, but we can return the message in logs or headers if needed
        # For now, we just return nothing with 204 status
        pass
    return None