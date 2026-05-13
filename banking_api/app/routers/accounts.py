"""
Account management router.
Handles account CRUD operations and balance adjustments.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.base import get_db_session
from app.repositories.account import AccountRepository
from app.schemas.account import (
    AccountCreate,
    AccountListResponse,
    AccountResponse,
    AccountUpdate,
    BalanceAdjustment,
)
from app.services.account import AccountService

logger = structlog.get_logger(__name__)

router = APIRouter()


def get_account_service(
    session: AsyncSession = Depends(get_db_session),
) -> AccountService:
    """Dependency to get account service with repository."""
    repo = AccountRepository(session)
    return AccountService(repo)


@router.post(
    "/",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new account",
)
async def create_account(
    account_data: AccountCreate,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    """
    Create a new bank account for a user.
    
    - **user_id**: Unique user identifier
    - **currency**: ISO 4217 currency code (default: USD)
    - **initial_balance**: Starting balance (must be >= 0)
    """
    account = await service.create_account(
        user_id=account_data.user_id,
        currency=account_data.currency,
        initial_balance=account_data.initial_balance,
    )
    
    logger.info(
        "Account created via API",
        account_id=str(account.account_id),
        user_id=account.user_id,
    )
    
    return AccountResponse.model_validate(account)


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    summary="Get account details",
)
async def get_account(
    account_id: uuid.UUID,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    """
    Get detailed information about a specific account.
    """
    account = await service.get_account(account_id)
    return AccountResponse.model_validate(account)


@router.get(
    "/user/{user_id}",
    response_model=AccountResponse,
    summary="Get account by user ID",
)
async def get_account_by_user(
    user_id: str,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    """
    Get account associated with a specific user.
    """
    account = await service.get_account_by_user(user_id)
    return AccountResponse.model_validate(account)


@router.get(
    "/",
    response_model=AccountListResponse,
    summary="List accounts",
)
async def list_accounts(
    skip: int = Query(default=0, ge=0, description="Offset"),
    limit: int = Query(default=100, ge=1, le=1000, description="Limit"),
    service: AccountService = Depends(get_account_service),
) -> AccountListResponse:
    """
    List all active accounts with pagination.
    """
    from app.repositories.account import AccountRepository
    from app.models.base import get_db_session
    
    async for session in get_db_session():
        repo = AccountRepository(session)
        accounts = await repo.get_active_accounts(skip=skip, limit=limit)
        total = await repo.count({"is_active": True})
        
        return AccountListResponse(
            items=[AccountResponse.model_validate(a) for a in accounts],
            total=total,
            page=(skip // limit) + 1,
            page_size=limit,
        )


@router.patch(
    "/{account_id}",
    response_model=AccountResponse,
    summary="Update account",
)
async def update_account(
    account_id: uuid.UUID,
    account_update: AccountUpdate,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    """
    Update account properties (e.g., activate/deactivate).
    """
    account = await service.get_account(account_id)
    
    update_data = account_update.model_dump(exclude_unset=True)
    if update_data:
        from app.repositories.account import AccountRepository
        from app.models.base import get_db_session
        
        async for session in get_db_session():
            repo = AccountRepository(session)
            account = await repo.update(account, update_data)
    
    return AccountResponse.model_validate(account)


@router.post(
    "/{account_id}/deposit",
    response_model=AccountResponse,
    summary="Deposit funds",
)
async def deposit_funds(
    account_id: uuid.UUID,
    deposit_data: BalanceAdjustment,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    """
    Deposit funds into an account.
    
    Requires **X-Idempotency-Key** header for idempotent operations.
    """
    account = await service.deposit(
        account_id=account_id,
        amount=deposit_data.amount,
        description=deposit_data.description,
        reference=deposit_data.reference,
    )
    
    return AccountResponse.model_validate(account)


@router.post(
    "/{account_id}/withdraw",
    response_model=AccountResponse,
    summary="Withdraw funds",
)
async def withdraw_funds(
    account_id: uuid.UUID,
    withdrawal_data: BalanceAdjustment,
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    """
    Withdraw funds from an account.
    
    Requires **X-Idempotency-Key** header for idempotent operations.
    """
    account = await service.withdraw(
        account_id=account_id,
        amount=withdrawal_data.amount,
        description=withdrawal_data.description,
        reference=withdrawal_data.reference,
    )
    
    return AccountResponse.model_validate(account)


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate account",
)
async def deactivate_account(
    account_id: uuid.UUID,
    service: AccountService = Depends(get_account_service),
) -> None:
    """
    Deactivate an account (soft delete).
    
    Account must have zero balance to be deactivated.
    """
    await service.deactivate_account(account_id)
