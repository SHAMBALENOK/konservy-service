from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None

class BaseResponse(BaseModel):
    success: bool = True
    message: str = "Operation successful"

# Common fields for account responses
class AccountBase(BaseModel):
    account_number: str = Field(..., example="ACC123456789")

class AccountCreate(AccountBase):
    user_id: int = Field(..., example=1)

class AccountResponse(AccountBase):
    id: int
    user_id: int
    balance: float = Field(..., example=1000.50)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Common fields for transaction responses
class TransactionBase(BaseModel):
    amount: float = Field(..., example=50.25)
    description: Optional[str] = Field(None, example="Salary deposit")

class TransactionCreate(TransactionBase):
    account_id: int = Field(..., example=1)
    transaction_type: str = Field(..., example="deposit")  # deposit, withdrawal, transfer
    # For transfers, we might need source and destination, but the endpoint design uses:
    #   POST /transfer with body having source and destination? Actually, the doc says:
    #   POST /api/v1/transactions/transfer
    #   and query parameter: current_user (source user ID)
    #   So we adjust: the transfer endpoint will take source_user_id (from query) and in body: destination_account_id and amount.
    #   However, to keep the TransactionCreate generic, we leave it to the specific endpoints to handle.

class TransactionResponse(TransactionBase):
    id: int
    account_id: int
    transaction_type: str
    status: str = Field(..., example="completed")
    created_at: datetime

    class Config:
        from_attributes = True