"""
Transaction management router.
Handles fund transfers, deposits, and transaction history.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import get_db_session
from app.repositories.account import AccountRepository
from app.repositories.transaction import TransactionRepository
from app.schemas.account import TransferRequest
from app.schemas.transaction import (
    TransactionListResponse,
    TransactionResponse,
)
from app.services.transaction import TransactionService

logger = structlog.get_logger(__name__)

router = APIRouter()


def get_transaction_service(
    session: AsyncSession = Depends(get_db_session),
) -> TransactionService:
    """Dependency to get transaction service with repositories."""
    transaction_repo = TransactionRepository(session)
    account_repo = AccountRepository(session)
    return TransactionService(transaction_repo, account_repo)


@router.post(
    "/transfer",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transfer funds between accounts",
)
async def transfer_funds(
    transfer_data: TransferRequest,
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
    current_user: str = Query(..., description="Source user ID"),
    service: TransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    """
    Transfer funds from the authenticated user's account to another account.
    
    - **destination_account_id**: Target account UUID
    - **amount**: Transfer amount (must be positive)
    - **description**: Optional transfer description
    - **X-Idempotency-Key**: Required header to prevent duplicate transfers
    """
    # Get source account for the current user
    account_repo = AccountRepository(next(get_db_session().__aiter__()))
    source_account = await account_repo.get_by_user_id(current_user)
    
    if not source_account:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(
            message=f"No account found for user {current_user}",
            error_code="ACCOUNT_NOT_FOUND",
        )
    
    transaction = await service.create_transfer(
        source_account_id=source_account.account_id,
        destination_account_id=transfer_data.destination_account_id,
        amount=transfer_data.amount,
        currency=transfer_data.currency,
        description=transfer_data.description,
        reference=transfer_data.reference,
        idempotency_key=x_idempotency_key,
    )
    
    logger.info(
        "Transfer initiated via API",
        transaction_id=str(transaction.transaction_id),
        source_account_id=str(source_account.account_id),
        destination_account_id=str(transfer_data.destination_account_id),
        amount=str(transfer_data.amount),
    )
    
    return TransactionResponse.model_validate(transaction)


@router.post(
    "/deposit",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Deposit funds to account",
)
async def deposit_funds(
    account_id: uuid.UUID = Query(..., description="Target account ID"),
    amount: float = Query(..., gt=0, description="Deposit amount"),
    currency: str = Query(default="USD", min_length=3, max_length=3),
    description: str | None = Query(None, max_length=500),
    reference: str | None = Query(None, max_length=255),
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
    service: TransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    """
    Deposit funds into an account.
    
    Requires **X-Idempotency-Key** header for idempotent operations.
    """
    from decimal import Decimal
    
    transaction = await service.create_deposit(
        account_id=account_id,
        amount=Decimal(str(amount)),
        currency=currency,
        description=description,
        reference=reference,
        idempotency_key=x_idempotency_key,
    )
    
    return TransactionResponse.model_validate(transaction)


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get transaction details",
)
async def get_transaction(
    transaction_id: uuid.UUID,
    service: TransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    """
    Get detailed information about a specific transaction.
    """
    transaction = await service.get_transaction(transaction_id)
    return TransactionResponse.model_validate(transaction)


@router.get(
    "/account/{account_id}",
    response_model=TransactionListResponse,
    summary="Get account transactions",
)
async def get_account_transactions(
    account_id: uuid.UUID,
    skip: int = Query(default=0, ge=0, description="Offset"),
    limit: int = Query(default=100, ge=1, le=1000, description="Limit"),
    service: TransactionService = Depends(get_transaction_service),
) -> TransactionListResponse:
    """
    Get transaction history for a specific account.
    """
    transactions = await service.get_account_transactions(
        account_id=account_id,
        skip=skip,
        limit=limit,
    )
    
    from app.repositories.transaction import TransactionRepository
    from app.models.base import get_db_session
    
    async for session in get_db_session():
        repo = TransactionRepository(session)
        total = await repo.count({})
        
        return TransactionListResponse(
            items=[TransactionResponse.model_validate(t) for t in transactions],
            total=total,
            page=(skip // limit) + 1,
            page_size=limit,
        )


@router.get(
    "/",
    response_model=TransactionListResponse,
    summary="List all transactions",
)
async def list_transactions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    service: TransactionService = Depends(get_transaction_service),
) -> TransactionListResponse:
    """
    List all transactions with pagination.
    """
    from app.repositories.transaction import TransactionRepository
    from app.models.base import get_db_session
    
    async for session in get_db_session():
        repo = TransactionRepository(session)
        transactions = await repo.get_all(skip=skip, limit=limit)
        total = await repo.count()
        
        return TransactionListResponse(
            items=[TransactionResponse.model_validate(t) for t in transactions],
            total=total,
            page=(skip // limit) + 1,
            page_size=limit,
        )
